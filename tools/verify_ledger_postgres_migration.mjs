import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {resolve} from 'node:path';
import {writeFile} from 'node:fs/promises';
import {DatabaseSync} from 'node:sqlite';

const [runtime, output, auditFixture] = process.argv.slice(2);
if (!runtime || !output) throw Error('Expected PGLITE_RUNTIME OUTPUT');
const require = createRequire(resolve(runtime, 'package.json'));
const {PGlite} = require('@electric-sql/pglite');
const {postgis} = require('@electric-sql/pglite-postgis');
const sqlite = new DatabaseSync(':memory:');
const postgres = new PGlite({extensions: {postgis}});
const columns = 'id,domain,entity,debit_account,credit_account,cents,evidence,created';
const totals = `
  WITH postings AS (
    SELECT domain, entity, debit_account AS account, cents FROM ledger
    UNION ALL SELECT domain, entity, credit_account, -cents FROM ledger
  )
  SELECT domain,entity,account,CAST(SUM(cents) AS text) AS cents
  FROM postings GROUP BY domain,entity,account ORDER BY domain,entity,account
`;
let report;
try {
  sqlite.exec(`CREATE TABLE ledger(id TEXT PRIMARY KEY,domain TEXT,entity TEXT,
    debit_account TEXT,credit_account TEXT,cents INTEGER,evidence TEXT,created TEXT)`);
  const insert = sqlite.prepare('INSERT INTO ledger VALUES (?,?,?,?,?,?,?,?)');
  for (const [id, domain, entity, debit, credit, cents] of [
    ['j1','FAMILY_OFFICE','Fixture A','Cash','Owner equity',100000000000n],
    ['j2','FAMILY_OFFICE','Fixture A','Maintenance expense','Cash',40701n],
    ['j3','COMMERCIAL','Fixture B','Cash','Service revenue',190099n],
    ['j4','COMMERCIAL','Fixture B','Property','Payable',100000000000n],
  ]) insert.run(id,domain,entity,debit,credit,cents,'Synthetic rehearsal evidence','2026-11-24T00:00:00.123456+00:00');
  const projection = `SELECT ${columns.replace('cents','CAST(cents AS text) AS cents')} FROM ledger ORDER BY id`;
  const source = sqlite.prepare(projection).all().map(row => ({...row}));
  await postgres.exec(`
    CREATE TABLE ledger(id text PRIMARY KEY, domain text NOT NULL, entity text NOT NULL,
      debit_account text NOT NULL, credit_account text NOT NULL,
      cents bigint NOT NULL CHECK(cents > 0 AND cents <= 100000000000),
      evidence text NOT NULL, created text NOT NULL, CHECK(debit_account <> credit_account));
  `);
  await postgres.exec(`
    CREATE EXTENSION postgis;
    CREATE TABLE migration_geometry (id text PRIMARY KEY, geom geometry(Point,4326));
    CREATE TABLE migration_audit (seq bigint PRIMARY KEY, body text NOT NULL, prev_hash text NOT NULL, hash text NOT NULL);
  `);
  await postgres.exec('BEGIN');
  let auditEvents = 0;
  if (auditFixture) {
    const input = new DatabaseSync(auditFixture, {readOnly: true});
    try {
      const audit = input.prepare('SELECT seq,body,prev_hash,hash FROM audit ORDER BY seq').all().map(row => ({...row}));
      assert.ok(audit.length);
      await postgres.query('INSERT INTO migration_audit SELECT * FROM jsonb_populate_recordset(NULL::migration_audit,$1::jsonb)', [JSON.stringify(audit)]);
      const readback = (await postgres.query('SELECT seq,body,prev_hash,hash FROM migration_audit ORDER BY seq')).rows;
      assert.deepEqual(readback, audit);
      let head = 'GENESIS';
      for (const event of readback) {
        assert.equal(event.prev_hash, head);
        head = createHash('sha256').update(head + event.body).digest('hex');
        assert.equal(event.hash, head);
      }
      auditEvents = readback.length;
    } finally {
      input.close();
    }
  }
  await postgres.exec("INSERT INTO migration_geometry VALUES ('fixture', ST_SetSRID(ST_Point(-81.38,28.58),4326))");
  const {rows: [geometry]} = await postgres.query('SELECT ST_SRID(geom) AS srid, ST_IsValid(geom) AS valid FROM migration_geometry');
  assert.deepEqual(geometry, {srid: 4326, valid: true});
  await postgres.query('INSERT INTO ledger SELECT * FROM jsonb_populate_recordset(NULL::ledger,$1::jsonb)', [JSON.stringify(source)]);
  assert.deepEqual((await postgres.query(projection)).rows, source);
  const balances = (await postgres.query(totals)).rows;
  assert.deepEqual(balances, sqlite.prepare(totals).all().map(row => ({...row})));
  for (const domain of new Set(balances.map(row => row.domain))) {
    assert.equal(balances.filter(row => row.domain === domain).reduce((sum,row) => sum + BigInt(row.cents), 0n), 0n);
  }
  await postgres.exec('ROLLBACK');
  for (const table of ['ledger', 'migration_geometry', 'migration_audit']) {
    assert.equal((await postgres.query(`SELECT 1 FROM ${table} LIMIT 1`)).rows.length, 0);
  }
  report = {ticket:'BR-T014', mode:'DISPOSABLE_SIMULATION_LEDGER', journals:source.length,
    account_balances:balances.length, exact_journal_and_balance_readback:true,
    zero_net_debits_less_credits_per_domain:true, rollback_verified:true,
    audit_events_verified:auditEvents, spatial_fixture_srid:geometry.srid, shared_transaction_rollback:true,
    production_cutover:false, independent_acceptance:null};
} finally {
  sqlite.close();
  await postgres.close();
}
await writeFile(output, JSON.stringify(report,null,2) + '\n', {flag:'wx'});
