import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFile, writeFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {resolve} from 'node:path';
import {DatabaseSync} from 'node:sqlite';

const [runtime, output] = process.argv.slice(2);
if (!runtime || !output) throw Error('Expected RUNTIME_DIR OUTPUT');
const require = createRequire(resolve(runtime, 'package.json'));
const {PGlite} = require('@electric-sql/pglite');
const {postgis} = require('@electric-sql/pglite-postgis');
const ddl = await readFile(new URL('../docs/postgres-target.sql', import.meta.url));
const db = new PGlite({extensions: {postgis}});
const sqlite = new DatabaseSync(':memory:');
const at = '2026-11-24T12:00:00.123456+00:00';
const fixture = [
  ['a1', 'COMMERCIAL', 'orange-1', 'FL:Orange', '001-02', 'rev1', at],
  ['a2', 'COMMERCIAL', 'orange-1', 'FL:Orange', '001-02', 'rev2', at],
  ['a3', 'COMMERCIAL', 'lake-1', 'FL:Lake', '001-02', 'rev1', at],
  ['a4', 'FAMILY_OFFICE', 'private-1', 'FL:Orange', '001-02', 'rev1', at],
];
try {
  sqlite.exec('CREATE TABLE aliases (id TEXT, domain TEXT, object_id TEXT, namespace TEXT, raw_identifier TEXT, source_revision TEXT, observed_at TEXT)');
  const insert = sqlite.prepare('INSERT INTO aliases VALUES (?,?,?,?,?,?,?)');
  for (const row of fixture) insert.run(...row);
  const rows = sqlite.prepare('SELECT * FROM aliases ORDER BY id').all().map(row => ({...row}));
  await db.exec(ddl.toString('utf8'));
  await db.exec('CREATE ROLE br_alias_reader NOLOGIN; GRANT SELECT, INSERT ON operational_aliases TO br_alias_reader');
  await db.exec('BEGIN');
  await db.exec(`INSERT INTO operational_objects (id,domain,object_type,title) VALUES
    ('orange-1','COMMERCIAL','Parcel','Orange fixture'),
    ('lake-1','COMMERCIAL','Parcel','Lake fixture'),
    ('private-1','FAMILY_OFFICE','Parcel','Private fixture')`);
  await db.query('INSERT INTO operational_aliases SELECT * FROM jsonb_populate_recordset(NULL::operational_aliases,$1::jsonb)', [JSON.stringify(rows)]);
  const exact = await db.query(`SELECT id,domain,object_id,namespace,raw_identifier,source_revision,
    to_char(observed_at AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS.US') || '+00:00' AS observed_at
    FROM operational_aliases ORDER BY id`);
  assert.deepEqual(exact.rows, rows);
  await db.exec('SET LOCAL ROLE br_alias_reader');
  assert.deepEqual((await db.query('SELECT id FROM operational_aliases')).rows, []);
  await db.exec("SET LOCAL br.allowed_domains = 'COMMERCIAL'");
  const matches = await db.query(`SELECT id FROM operational_aliases
    WHERE namespace=$1 AND raw_identifier=$2 ORDER BY id`, ['FL:Orange','001-02']);
  assert.deepEqual(matches.rows, [{id:'a1'},{id:'a2'}]);
  await db.exec('SAVEPOINT cross_domain');
  await assert.rejects(db.query('INSERT INTO operational_aliases VALUES ($1,$2,$3,$4,$5,$6,$7)',
    ['bad','COMMERCIAL','private-1','FL:Orange','001-02','rev3',at]), {code:'23503'});
  await db.exec('ROLLBACK TO SAVEPOINT cross_domain');
  await db.exec('ROLLBACK');
  assert.equal((await db.query('SELECT count(*)::integer AS n FROM operational_aliases')).rows[0].n, 0);
  await writeFile(output, JSON.stringify({
    ticket:'BR-T014', mode:'DISPOSABLE_SQLITE_TO_EMBEDDED_POSTGIS',
    fixture:'synthetic parcel alias rows', aliases:rows.length, exact_round_trip:true,
    county_namespace_scoped:true, revision_history_preserved:true, default_deny:true,
    cross_domain_foreign_key_rejected:true, rollback_verified:true,
    ddl_sha256:createHash('sha256').update(ddl).digest('hex'),
  }, null, 2) + '\n');
} finally {
  sqlite.close();
  await db.close();
}
