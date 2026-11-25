import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFile, writeFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {resolve} from 'node:path';
import {loadCollegePark, prepareParcelReader, verifySpatialAliases} from './postgres_parcel_rehearsal.mjs';

const [runtime, source, output] = process.argv.slice(2);
if (!runtime || !source || !output) throw Error('Expected RUNTIME_DIR SOURCE_GPKG OUTPUT');
const require = createRequire(resolve(runtime, 'package.json'));
const {PGlite} = require('@electric-sql/pglite');
const {postgis} = require('@electric-sql/pglite-postgis');
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const ddl = await readFile(new URL('../docs/postgres-target.sql', import.meta.url));
const spatialInput = await loadCollegePark(source);

const db = new PGlite({extensions: {postgis}});
let report;
try {
  await db.exec(ddl.toString('utf8'));
  const {rows: [versions]} = await db.query("SELECT version() AS postgres, postgis_version() AS postgis");
  await prepareParcelReader(db);
  await db.exec('BEGIN');
  const spatial = await verifySpatialAliases(db, spatialInput);
  await db.exec('ROLLBACK');
  assert.equal((await db.query('SELECT id FROM operational_objects LIMIT 1')).rows.length, 0);
  assert.equal((await db.query('SELECT id FROM operational_aliases LIMIT 1')).rows.length, 0);
  report = {ticket: 'BR-T014', mode: 'DISPOSABLE_GPKG_TO_EMBEDDED_POSTGIS', ...versions,
    ...spatial, ddl_sha256: hash(ddl), alias_scope_and_spatial_join_verified: true,
    identical_ids_and_attributes: true, geometry_valid_srid_4326: true, rollback_verified: true,
    full_application_snapshot_migrated: false, production_cutover: false, independent_acceptance: null};
} finally {
  await db.close();
}
await writeFile(output, JSON.stringify(report, null, 2) + '\n', {flag: 'wx'});
