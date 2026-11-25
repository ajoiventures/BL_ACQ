import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFile, writeFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {resolve} from 'node:path';
import {DatabaseSync} from 'node:sqlite';
import {loadCollegePark, prepareParcelReader, verifySpatialAliases} from './postgres_parcel_rehearsal.mjs';

const [runtime, source, output, spatialSource] = process.argv.slice(2);
if (!runtime || !source || !output) throw Error('Expected RUNTIME_DIR SQLITE_FIXTURE OUTPUT [COLLEGE_PARK_GPKG]');
const require = createRequire(resolve(runtime, 'package.json'));
const {PGlite} = require('@electric-sql/pglite');
const {postgis} = require('@electric-sql/pglite-postgis');
const ddl = await readFile(new URL('../docs/postgres-target.sql', import.meta.url));
const evidenceDdl = await readFile(new URL('../docs/postgres-evidence-target.sql', import.meta.url));
const utc = column => `to_char(${column} AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US') || '+00:00' AS ${column}`;
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const sqlite = new DatabaseSync(source, {readOnly: true});
let objects;
let links;
let evidence;
let assertions;
let audit;
let ledger;
try {
  sqlite.exec('BEGIN');
  audit = sqlite.prepare('SELECT seq,domain,actor,action,object_id,body,prev_hash,hash,at FROM audit ORDER BY seq').all().map(row => ({...row}));
  ledger = sqlite.prepare('SELECT id,domain,entity,debit_account,credit_account,CAST(cents AS text) AS cents,evidence,created FROM ledger ORDER BY id').all().map(row => ({...row}));
  objects = sqlite.prepare('SELECT id,type AS object_type,domain,title,properties,created_at FROM objects ORDER BY id').all()
    .map(row => ({...row, properties: JSON.parse(row.properties)}));
  links = sqlite.prepare('SELECT id,domain,src AS source_id,dst AS destination_id,type AS relationship,source_id AS evidence_id,created_at FROM links ORDER BY id').all()
    .map(row => ({...row}));
  evidence = sqlite.prepare('SELECT * FROM evidence ORDER BY id').all().map(row => ({...row}));
  assertions = sqlite.prepare('SELECT s.*, o.domain FROM statuses s JOIN objects o ON o.id=s.subject_id ORDER BY s.id').all()
    .map(row => ({...row, rights: JSON.parse(row.rights), obligations: JSON.parse(row.obligations),
      prohibitions: JSON.parse(row.prohibitions)}));
} finally {
  sqlite.close();
}
assert.ok(objects.length && links.length, 'Populated object/link fixture required');
const spatialInput = spatialSource ? await loadCollegePark(spatialSource) : null;
const db = new PGlite({extensions: {postgis}});
let report;
try {
  await db.exec(ddl.toString('utf8'));
  await db.exec(evidenceDdl.toString('utf8'));
  await db.exec('ALTER TABLE operational_links ADD COLUMN created_at timestamptz NOT NULL');
  await db.exec(`
    CREATE ROLE br_migration_reader NOLOGIN;
    GRANT SELECT, INSERT ON operational_evidence, operational_assertions TO br_migration_reader;
  `);
  await db.exec(`
    CREATE TABLE migration_audit (seq bigint PRIMARY KEY, domain text, actor text, action text,
      object_id text, body text NOT NULL, prev_hash text NOT NULL, hash text NOT NULL, at text);
    CREATE TABLE migration_ledger (id text PRIMARY KEY, domain text NOT NULL, entity text NOT NULL,
      debit_account text NOT NULL, credit_account text NOT NULL,
      cents bigint NOT NULL CHECK(cents > 0), evidence text NOT NULL, created text NOT NULL,
      CHECK(debit_account <> credit_account));
  `);
  if (spatialInput) await prepareParcelReader(db);
  await db.exec('BEGIN');
  await db.query('INSERT INTO migration_audit SELECT * FROM jsonb_populate_recordset(NULL::migration_audit,$1::jsonb)', [JSON.stringify(audit)]);
  await db.query('INSERT INTO migration_ledger SELECT * FROM jsonb_populate_recordset(NULL::migration_ledger,$1::jsonb)', [JSON.stringify(ledger)]);
  const auditReadback = (await db.query('SELECT * FROM migration_audit ORDER BY seq')).rows;
  assert.deepEqual(auditReadback, audit);
  let head = 'GENESIS';
  for (const event of auditReadback) {
    assert.equal(event.prev_hash, head);
    head = sha(head + event.body);
    assert.equal(event.hash, head);
  }
  const ledgerReadback = (await db.query(`
    SELECT id,domain,entity,debit_account,credit_account,cents::text AS cents,evidence,created
    FROM migration_ledger ORDER BY id
  `)).rows;
  assert.deepEqual(ledgerReadback, ledger);

  await db.query(`
    INSERT INTO operational_objects(id,object_type,domain,title,properties,created_at)
    SELECT id,object_type,domain,title,properties,created_at
    FROM jsonb_populate_recordset(NULL::operational_objects,$1::jsonb)
  `, [JSON.stringify(objects)]);
  await db.query('INSERT INTO operational_links SELECT * FROM jsonb_populate_recordset(NULL::operational_links,$1::jsonb)', [JSON.stringify(links)]);
  for (const [table, records] of [['operational_evidence', evidence], ['operational_assertions', assertions]]) {
    await db.query(`INSERT INTO ${table} SELECT * FROM jsonb_populate_recordset(NULL::${table},$1::jsonb)`,
      [JSON.stringify(records)]);
  }
  const exactEvidence = (await db.query(`
    SELECT id,object_id,domain,source_uri,kind,source_date::text AS source_date,content_hash,${utc('recorded_at')}
    FROM operational_evidence ORDER BY id COLLATE "C"
  `)).rows;
  const exactAssertions = (await db.query(`
    SELECT id,subject_id,domain,predicate,value,context,authority,rights,obligations,prohibitions,
          ${utc('effective_at')},${utc('expires_at')},verification,source_evidence,verified_by,${utc('created_at')}
    FROM operational_assertions ORDER BY id COLLATE "C"
  `)).rows;
  assert.deepEqual(exactEvidence, evidence);
  assert.deepEqual(exactAssertions, assertions);
  let temporalCases = 0;
  for (const cutoff of [
    '2026-11-24T01:02:03.000000+00:00',
    '2026-11-24T01:02:03.000001+00:00',
    '2026-12-31T23:59:59.999999+00:00',
    '2027-01-01T00:00:00.000000+00:00',
  ]) {
    const {rows} = await db.query(`
      SELECT id, CASE
        WHEN expires_at <= $1::timestamptz THEN 'EXPIRED'
        WHEN effective_at > $1::timestamptz THEN 'NOT_YET_EFFECTIVE'
        ELSE verification
      END AS effective_verification
      FROM operational_assertions ORDER BY id COLLATE "C"
    `, [cutoff]);
    // Readback already proved that the fixture timestamps use canonical UTC strings.
    const expected = assertions.map(row => ({
      id: row.id,
      effective_verification: row.expires_at && row.expires_at <= cutoff ? 'EXPIRED'
        : row.effective_at > cutoff ? 'NOT_YET_EFFECTIVE' : row.verification,
    }));
    assert.deepEqual(rows, expected);
    temporalCases += rows.length;
  }

  const timestamp = "to_char(created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS.US') || '+00:00' AS created_at";
  const actualObjects = (await db.query(`SELECT id,object_type,domain,title,properties,${timestamp} FROM operational_objects ORDER BY id COLLATE "C"`)).rows;
  const actualLinks = (await db.query(`SELECT id,domain,source_id,destination_id,relationship,evidence_id,${timestamp} FROM operational_links ORDER BY id COLLATE "C"`)).rows;
  assert.deepEqual(actualObjects, objects);
  assert.deepEqual(actualLinks, links);
  const domains = [...new Set(assertions.map(row => row.domain))].sort();
  let domainIsolationVerified = false;
  let invalidWritesRejected = false;
  if (domains.length >= 2) {
    await db.exec('SET LOCAL ROLE br_migration_reader');
    assert.equal((await db.query('SELECT id FROM operational_evidence')).rows.length, 0);
    assert.equal((await db.query('SELECT id FROM operational_assertions')).rows.length, 0);
    for (const domain of domains) {
      await db.query("SELECT set_config('br.allowed_domains', $1, true)", [domain]);
      for (const [table, expected] of [['operational_evidence', evidence], ['operational_assertions', assertions]]) {
        const scoped = (await db.query(`SELECT id,domain FROM ${table} ORDER BY id COLLATE "C"`)).rows;
        assert.deepEqual(scoped, expected.filter(row => row.domain === domain).map(row => ({id: row.id, domain})));
      }
    }
    const [allowed, denied] = domains;
    const subject = assertions.find(row => row.domain === allowed);
    const other = assertions.find(row => row.domain === denied);
    await db.query("SELECT set_config('br.allowed_domains', $1, true)", [allowed]);
    await db.exec('SAVEPOINT forbidden_write');
    await assert.rejects(db.query(
      'INSERT INTO operational_assertions SELECT * FROM jsonb_populate_record(NULL::operational_assertions,$1::jsonb)',
      [JSON.stringify({...other, id: 'fixture-forbidden-write'})]
    ), {code: '42501'});
    await db.exec('ROLLBACK TO forbidden_write; SAVEPOINT wrong_evidence');
    await assert.rejects(db.query(
      'INSERT INTO operational_assertions SELECT * FROM jsonb_populate_record(NULL::operational_assertions,$1::jsonb)',
      [JSON.stringify({...subject, id: 'fixture-wrong-evidence', source_evidence: other.source_evidence})]
    ), {code: '23503'});
    await db.exec('ROLLBACK TO wrong_evidence');
    invalidWritesRejected = true;
    domainIsolationVerified = true;
    await db.exec('RESET ROLE');
  }
  const spatial = spatialInput ? await verifySpatialAliases(db, spatialInput) : null;
  await db.exec('ROLLBACK');
  for (const table of ['operational_objects', 'operational_links', 'operational_evidence', 'operational_assertions', 'migration_audit', 'migration_ledger', 'operational_aliases']) {
    assert.equal((await db.query(`SELECT 1 FROM ${table} LIMIT 1`)).rows.length, 0);
  }
  report = {ticket: 'BR-T014', mode: 'DISPOSABLE_TYPED_ONTOLOGY_MIGRATION', source_sha256: sha(await readFile(source)),
    base_ddl_sha256: sha(ddl), objects: objects.length, links: links.length,
    link_timestamp_column_added_for_rehearsal: true, exact_object_and_link_readback: true,
    evidence_ddl_sha256: sha(evidenceDdl), evidence_rows: evidence.length, assertion_rows: assertions.length,
    exact_evidence_and_assertion_readback: true, tested_domains: domains,
    domain_isolation_verified: domainIsolationVerified, invalid_writes_rejected: invalidWritesRejected,
    spatial_alias_rehearsal: spatial,
    audit_events: audit.length, journal_rows: ledger.length, exact_audit_and_journal_readback: true,
    temporal_projection_cases: temporalCases, rollback_verified: true, independent_acceptance: null, cutover_performed: false};
} finally {
  await db.close();
}
await writeFile(output, JSON.stringify(report, null, 2) + '\n', {flag: 'wx'});
