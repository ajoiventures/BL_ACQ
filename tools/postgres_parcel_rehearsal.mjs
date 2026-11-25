import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFile} from 'node:fs/promises';
import {DatabaseSync} from 'node:sqlite';

const hash = bytes => createHash('sha256').update(bytes).digest('hex');

export async function loadCollegePark(source) {
  const sourceDigest = hash(await readFile(source));
  const receipt = JSON.parse(await readFile(new URL('../docs/acquisition/college-park-coverage/college-park-survey-exchange.json', import.meta.url), 'utf8'));
  assert.equal(sourceDigest, receipt.outputs.GPKG.sha256);

  const sqlite = new DatabaseSync(source, {readOnly: true});
  let parcels;
  try {
    const [geometryColumn] = sqlite.prepare('SELECT srs_id, geometry_type_name FROM gpkg_geometry_columns').all();
    assert.equal(geometryColumn.srs_id, 2236);
    assert.equal(geometryColumn.geometry_type_name, 'MULTIPOLYGON');
    parcels = sqlite.prepare('SELECT * FROM college_park ORDER BY county_parcel_id').all().map(row => {
      const geom = Buffer.from(row.geom);
      assert.equal(geom.subarray(0, 2).toString(), 'GP');
      assert.equal(geom.readUInt8(2), 0);
      const flags = geom.readUInt8(3);
      assert.equal(flags & 0xf0, 0);
      assert.equal(flags & 1 ? geom.readInt32LE(4) : geom.readInt32BE(4), 2236);
      const envelope = [0, 32, 48, 48, 64][(flags >> 1) & 7];
      assert.notEqual(envelope, undefined);
      const wkb = geom.subarray(8 + envelope);
      assert.match(row.county_parcel_id, /^\d{15}$/);
      return {
        id: '12095:' + row.county_parcel_id, wkb: wkb.toString('hex'),
        properties: {county_parcel_id: row.county_parcel_id, county_object_ids: row.county_object_ids,
          parcel_area_us_survey_sqft: row.parcel_area_us_survey_sqft,
          overlap_us_survey_sqft: row.overlap_us_survey_sqft, overlap_fraction: row.overlap_fraction},
      };
    });
  } finally {
    sqlite.close();
  }
  assert.equal(parcels.length, receipt.outputs.GPKG.rows);

  return {parcels, sourceDigest};
}

export async function prepareParcelReader(db) {
  await db.exec('CREATE ROLE br_parcel_reader NOLOGIN; GRANT SELECT ON operational_objects, operational_aliases TO br_parcel_reader');
}

export async function verifySpatialAliases(db, {parcels, sourceDigest}) {
  for (let offset = 0; offset < parcels.length; offset += 128) {
    const batch = parcels.slice(offset, offset + 128);
    await db.query(`
      INSERT INTO operational_objects (id, domain, object_type, title, properties, geometry, original_crs, source_uri)
      SELECT item->>'id', 'COMMERCIAL', 'PARCEL', item->>'id', item->'properties',
             ST_Transform(ST_GeomFromWKB(decode(item->>'wkb','hex'),2236),4326),
             'EPSG:2236', $2
      FROM jsonb_array_elements($1::jsonb) AS item
    `, [JSON.stringify(batch), 'sha256:' + sourceDigest]);
  }
  await db.query(`
    INSERT INTO operational_aliases
      (id,domain,object_id,namespace,raw_identifier,source_revision,observed_at)
    SELECT id || ':county-parcel-id', domain, id, 'US:12095:parcel-id',
           properties->>'county_parcel_id', $1, transaction_timestamp()
    FROM operational_objects WHERE source_uri=$2
  `, [sourceDigest, 'sha256:' + sourceDigest]);
  await db.exec("SAVEPOINT parcel_scope; SET LOCAL ROLE br_parcel_reader; SET LOCAL br.allowed_domains = ''");
  assert.equal((await db.query('SELECT id FROM operational_aliases LIMIT 1')).rows.length, 0);
  await db.exec("SET LOCAL br.allowed_domains = 'COMMERCIAL'");
  const aliases = (await db.query(`
    SELECT a.raw_identifier, a.object_id, a.source_revision, ST_SRID(o.geometry) AS srid
    FROM operational_aliases a JOIN operational_objects o
      ON o.id=a.object_id AND o.domain=a.domain
    WHERE a.namespace='US:12095:parcel-id' ORDER BY a.object_id
  `)).rows;
  assert.deepEqual(aliases, parcels.map(parcel => ({
    raw_identifier: parcel.properties.county_parcel_id, object_id: parcel.id,
    source_revision: sourceDigest, srid: 4326,
  })));
  await db.exec("SET LOCAL br.allowed_domains = 'FAMILY_OFFICE'");
  assert.equal((await db.query('SELECT id FROM operational_aliases LIMIT 1')).rows.length, 0);
  await db.exec('ROLLBACK TO parcel_scope; RELEASE parcel_scope');
  const {rows} = await db.query(`
    SELECT id, properties, ST_SRID(geometry) AS srid, ST_IsValid(geometry) AS valid,
           ST_Area(ST_Transform(geometry,2236)) AS area
    FROM operational_objects WHERE source_uri=$1 ORDER BY id
  `, ['sha256:' + sourceDigest]);
  assert.equal(rows.length, parcels.length);
  let maxAreaDifference = 0;
  for (const [index, row] of rows.entries()) {
    const original = parcels[index];
    assert.equal(row.id, original.id);
    assert.deepEqual(row.properties, original.properties);
    assert.equal(row.srid, 4326);
    assert.equal(row.valid, true);
    maxAreaDifference = Math.max(maxAreaDifference, Math.abs(row.area - original.properties.parcel_area_us_survey_sqft));
  }
  assert.ok(maxAreaDifference < 0.01, String(maxAreaDifference));
  return {source_sha256: sourceDigest, rows: rows.length, aliases: aliases.length, maxAreaDifference};
}
