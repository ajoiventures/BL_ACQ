import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {open, readFile, writeFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {resolve} from 'node:path';
import {DatabaseSync, backup} from 'node:sqlite';

const [runtime, source, output, restoredOutput] = process.argv.slice(2);
if (!runtime || !source || !output) throw Error('Expected RUNTIME_DIR SQLITE_FIXTURE RECEIPT [RESTORED_SQLITE]');
const {PGlite} = createRequire(resolve(runtime, 'package.json'))('@electric-sql/pglite');
const hash = input => createHash('sha256').update(input).digest('hex');
const ident = value => '"' + value.replaceAll('"', '""') + '"';
function tagged(value) {
  if (value instanceof Uint8Array) return ['blob', Buffer.from(value).toString('hex')];
  if (typeof value === 'bigint') return ['integer', value.toString()];
  if (typeof value === 'number') {
    const bytes = Buffer.allocUnsafe(8);
    bytes.writeDoubleBE(value);
    return ['real', bytes.toString('hex')];
  }
  return value === null ? ['null', null] : ['text', value];
}
function update(digest, row) {
  digest.update(JSON.stringify(row) + '\n');
}

const sqlite = new DatabaseSync(source, {readOnly: true});
const db = new PGlite();
const restored = new DatabaseSync(':memory:');
function untag([, type, value]) {
  if (type === 'integer') return BigInt(value);
  if (type === 'real') return Buffer.from(value, 'hex').readDoubleBE();
  if (type === 'blob') return Buffer.from(value, 'hex');
  if (type === 'text' || type === 'null') return value;
  throw Error('Unknown SQLite storage class');
}
let report;
try {
  sqlite.exec('BEGIN');
  assert.equal(sqlite.prepare('PRAGMA integrity_check').get().integrity_check, 'ok');
  const schema = sqlite.prepare("SELECT type,name,tbl_name,sql FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").all().map(row => ({...row}));
  const tables = schema.filter(row => row.type === 'table');
  assert.ok(tables.length);
  await db.exec(`
    CREATE TABLE snapshot_schema(ordinal int PRIMARY KEY, descriptor jsonb NOT NULL);
    CREATE TABLE snapshot_rows(table_name text NOT NULL, ordinal bigint NOT NULL,
      cells jsonb NOT NULL, PRIMARY KEY(table_name, ordinal));
  `);
  await db.exec('BEGIN');
  await db.query('INSERT INTO snapshot_schema SELECT n, item FROM jsonb_array_elements($1::jsonb) WITH ORDINALITY AS x(item,n)', [JSON.stringify(schema)]);
  const stagedSchema = (await db.query('SELECT descriptor FROM snapshot_schema ORDER BY ordinal')).rows.map(row => row.descriptor);
  assert.deepEqual(stagedSchema, schema);
  restored.exec('PRAGMA foreign_keys=OFF; BEGIN');
  for (const table of stagedSchema.filter(row => row.type === 'table')) restored.exec(table.sql);
  const coverage = [];
  for (const {name} of tables) {
    const statement = sqlite.prepare(`SELECT * FROM ${ident(name)}`);
    statement.setReadBigInts(true);
    const expected = createHash('sha256');
    let count = 0;
    let batch = [];
    const flush = async () => {
      await db.query(`
        INSERT INTO snapshot_rows SELECT $1, $2::bigint + n, item
        FROM jsonb_array_elements($3::jsonb) WITH ORDINALITY AS x(item,n)
      `, [name, count - batch.length, JSON.stringify(batch)]);
      batch = [];
    };
    for (const row of statement.iterate()) {
      const cells = Object.entries(row).map(([key, value]) => [key, ...tagged(value)]);
      update(expected, cells);
      batch.push(cells);
      count++;
      if (batch.length === 128) await flush();
    }
    if (batch.length) await flush();
    const observed = createHash('sha256');
    const expectedRows = [];
    let insert;

    for (let offset = 0; offset < count; offset += 128) {
      const {rows} = await db.query(`
        SELECT cells FROM snapshot_rows WHERE table_name=$1 AND ordinal>$2
        ORDER BY ordinal LIMIT 128
      `, [name, offset]);
      assert.equal(rows.length, Math.min(128, count - offset));
      for (const row of rows) {
        update(observed, row.cells);
        expectedRows.push(JSON.stringify(row.cells));
        if (!insert) {
          const names = row.cells.map(cell => ident(cell[0]));
          insert = restored.prepare(`INSERT INTO ${ident(name)} (${names.join(',')}) VALUES (${names.map(() => '?').join(',')})`);
        }
        insert.run(...row.cells.map(untag));
      }
    }
    const digest = expected.digest('hex');
    assert.equal(observed.digest('hex'), digest, name);
    const restoredRows = restored.prepare(`SELECT * FROM ${ident(name)}`);
    restoredRows.setReadBigInts(true);
    const actual = restoredRows.all().map(row => JSON.stringify(Object.entries(row)
      .map(([key, value]) => [key, ...tagged(value)])));
    assert.deepEqual(actual.sort(), expectedRows.sort(), name);
    coverage.push({table: name, rows: count, row_sequence_sha256: digest});
  }
  for (const item of stagedSchema) {
    if (item.type !== 'table' && item.sql) restored.exec(item.sql);
  }
  restored.exec('COMMIT');
  const restoredSchema = restored.prepare("SELECT type,name,tbl_name,sql FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").all().map(row => ({...row}));
  assert.deepEqual(restoredSchema, schema);
  assert.equal(restored.prepare('PRAGMA integrity_check').get().integrity_check, 'ok');
  assert.deepEqual(restored.prepare('PRAGMA foreign_key_check').all(), []);
  await db.exec('ROLLBACK');
  assert.equal((await db.query('SELECT 1 FROM snapshot_rows LIMIT 1')).rows.length, 0);
  assert.equal((await db.query('SELECT 1 FROM snapshot_schema LIMIT 1')).rows.length, 0);
  report = {ticket: 'BR-T014', mode: 'SQLITE_TO_EMBEDDED_POSTGRES_LOSSLESS_STAGING',
    source_file_sha256: hash(await readFile(source)), schema_objects: schema.length, tables: coverage,
    total_rows: coverage.reduce((n, row) => n + row.rows, 0), rollback_verified: true, sqlite_rebuild_from_postgres_verified: true,
    production_schema_mapped: false, cutover_performed: false, independent_acceptance: null};
  if (restoredOutput) {
    const file = await open(restoredOutput, 'wx');
    await file.close();
    await backup(restored, restoredOutput);
    report.restored_file_sha256 = hash(await readFile(restoredOutput));
  }
} finally {
  sqlite.close();
  restored.close();
  await db.close();
}
await writeFile(output, JSON.stringify(report, null, 2) + '\n', {flag: 'wx'});
