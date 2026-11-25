import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFile, writeFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {resolve} from 'node:path';

const [runtime, output] = process.argv.slice(2);
if (!runtime || !output) throw new Error('Usage: node tools/verify_postgres_target.mjs RUNTIME_DIR OUTPUT');
const require = createRequire(resolve(runtime, 'package.json'));
const {PGlite} = require('@electric-sql/pglite');
const {postgis} = require('@electric-sql/pglite-postgis');
const ddl = await readFile(new URL('../docs/postgres-target.sql', import.meta.url));
const db = new PGlite({extensions: {postgis}});
let report;
try {
  await db.exec(ddl.toString('utf8'));
  const {rows: [versions]} = await db.query('SELECT version() AS postgres, postgis_full_version() AS postgis');
  await db.exec(`
    INSERT INTO operational_objects (id,domain,object_type,title,geometry)
    VALUES ('commercial-a','COMMERCIAL','PARCEL','Fixture A',ST_SetSRID(ST_Point(-81.38,28.58),4326)),
           ('family-a','FAMILY_OFFICE','ASSET','Fixture B',NULL);
    CREATE ROLE br_rehearsal NOLOGIN;
    GRANT SELECT, INSERT ON operational_objects, operational_links TO br_rehearsal;
    SET ROLE br_rehearsal;
  `);
  assert.equal((await db.query('SELECT id FROM operational_objects')).rows.length, 0);

  await db.exec("BEGIN; SET LOCAL br.allowed_domains = 'COMMERCIAL'");
  const {rows} = await db.query('SELECT id, ST_SRID(geometry) AS srid FROM operational_objects ORDER BY id');
  assert.deepEqual(rows, [{id: 'commercial-a', srid: 4326}]);
  await db.exec(`
    INSERT INTO operational_objects (id,domain,object_type,title)
    VALUES ('commercial-b','COMMERCIAL','PARCEL','Fixture C');
    INSERT INTO operational_links (id,domain,source_id,destination_id,relationship)
    VALUES ('valid','COMMERCIAL','commercial-a','commercial-b','ADJACENT');
    SAVEPOINT rls;
  `);
  await assert.rejects(db.exec("INSERT INTO operational_objects (id,domain,object_type,title) VALUES ('denied','FAMILY_OFFICE','ASSET','Denied')"), {code: '42501'});
  await db.exec('ROLLBACK TO rls; SAVEPOINT fk');
  await assert.rejects(db.exec("INSERT INTO operational_links (id,domain,source_id,destination_id,relationship) VALUES ('cross','COMMERCIAL','commercial-a','family-a','ADJACENT')"), {code: '23503'});
  await db.exec('ROLLBACK TO fk; ROLLBACK');
  assert.equal((await db.query('SELECT id FROM operational_objects')).rows.length, 0);

  await db.exec('RESET ROLE');
  assert.deepEqual((await db.query('SELECT id FROM operational_objects ORDER BY id')).rows.map(row => row.id), ['commercial-a', 'family-a']);
  assert.equal((await db.query('SELECT id FROM operational_links')).rows.length, 0);
  report = {
    ticket: 'BR-T014', mode: 'PGLITE_POSTGIS_DISPOSABLE_SCHEMA_FIXTURE', ...versions,
    ddl_sha256: createHash('sha256').update(ddl).digest('hex'),
    verified: ['Default-deny read', 'Scoped read with SRID 4326', 'Cross-domain insert denied', 'Cross-domain link rejected', 'Rollback restored rows and cleared domain scope'],
    full_snapshot_migrated: false, production_cutover: false, independent_acceptance: null,
  };
} finally {
  await db.close();
}
await writeFile(output, JSON.stringify(report, null, 2) + '\n', {flag: 'wx'});
