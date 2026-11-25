import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFile, writeFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {resolve} from 'node:path';
import {DatabaseSync} from 'node:sqlite';

const [runtime, source, output] = process.argv.slice(2);
if (!runtime || !source || !output) throw Error('Expected RUNTIME_DIR SQLITE_FIXTURE OUTPUT');
const require = createRequire(resolve(runtime, 'package.json'));
const {PGlite} = require('@electric-sql/pglite');
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const sqlite = new DatabaseSync(source, {readOnly: true});
let tickets;
let audit;
try {
  assert.equal(sqlite.prepare('PRAGMA integrity_check').get().integrity_check, 'ok');
  tickets = sqlite.prepare('SELECT * FROM project_tickets ORDER BY id').all().map(row => ({...row}));
  audit = sqlite.prepare('SELECT * FROM audit ORDER BY seq').all().map(row => ({...row}));
} finally {
  sqlite.close();
}
assert.ok(tickets.length > 0 && audit.length > 0);
const ids = new Set(tickets.map(row => row.id));
assert.equal(ids.size, tickets.length);
assert.ok(tickets.every(row => JSON.parse(row.dependencies).every(id => ids.has(id))));

const db = new PGlite();
let report;
try {
  await db.exec(`
    CREATE TABLE project_tickets(id text PRIMARY KEY, area text NOT NULL, domain text NOT NULL,
      title text NOT NULL, leader text NOT NULL, owner text NOT NULL, status text NOT NULL,
      acceptance text NOT NULL, evidence text NOT NULL, dependencies text NOT NULL,
      version integer NOT NULL, source text NOT NULL);
    CREATE TABLE audit(seq bigint PRIMARY KEY, domain text, actor text, action text,
      object_id text, body text NOT NULL, prev_hash text NOT NULL, hash text NOT NULL, at text);

  `);
  await db.exec('BEGIN');
  for (const [table, rows] of [['project_tickets', tickets], ['audit', audit]]) {
    for (let offset = 0; offset < rows.length; offset += 128) {
      await db.query(`INSERT INTO ${table} SELECT * FROM jsonb_populate_recordset(NULL::${table}, $1::jsonb)`,
        [JSON.stringify(rows.slice(offset, offset + 128))]);
    }
  }
  const importedTickets = (await db.query('SELECT * FROM project_tickets ORDER BY id COLLATE "C"')).rows;
  const importedAudit = (await db.query('SELECT * FROM audit ORDER BY seq')).rows;
  assert.deepEqual(importedTickets, tickets);
  assert.deepEqual(importedAudit, audit);
  let head = 'GENESIS';
  for (const row of importedAudit) {
    assert.equal(row.prev_hash, head);
    assert.equal(row.hash, sha(head + row.body));
    head = row.hash;
  }
  await db.exec('ROLLBACK');
  for (const table of ['project_tickets', 'audit']) {
    assert.equal((await db.query(`SELECT 1 FROM ${table} LIMIT 1`)).rows.length, 0);
  }
  report = {ticket: 'BR-T014', mode: 'DISPOSABLE_SQLITE_TICKET_AUDIT_TO_EMBEDDED_POSTGRES',
    source_sha256: sha(await readFile(source)), tickets: tickets.length, audit_events: audit.length,
    audit_head_sha256: head, exact_row_and_audit_text_parity: true,
    ticket_dependencies_resolved: true, rollback_verified: true,
    full_application_snapshot_migrated: false, independent_acceptance: null};
} finally {
  await db.close();
}
await writeFile(output, JSON.stringify(report, null, 2) + '\n', {flag: 'wx'});
