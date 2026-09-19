\set ON_ERROR_STOP on
-- Real database checks for the bounded experimental profile; no product claims.
SET postgis.gdal_enabled_drivers = 'GTiff';
CREATE TEMP TABLE probe_results (test text PRIMARY KEY, passed boolean NOT NULL CHECK (passed));
CREATE FUNCTION pg_temp.assert(condition boolean, test_name text) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
  IF condition IS DISTINCT FROM true THEN
    RAISE EXCEPTION 'AmbisGIS probe failed: %', test_name;
  END IF;
  INSERT INTO probe_results VALUES (test_name, true);
END $$;
SELECT version(), postgis_full_version(), postgis_gdal_version();
SELECT pg_temp.assert(ST_Area(ST_Buffer(ST_Point(0,0), 1)) BETWEEN 3.1 AND 3.2,
                      'geometry buffer and area');
SELECT pg_temp.assert(ST_Equals(ST_Intersection(ST_MakeEnvelope(0,0,2,2),
  ST_MakeEnvelope(1,1,3,3)), ST_MakeEnvelope(1,1,2,2)), 'GEOS intersection');
CREATE TEMP TABLE probe_points AS SELECT i AS id,
  ST_SetSRID(ST_MakePoint(i % 100, i / 100), 4326) AS geom FROM generate_series(0,9999) i;
CREATE INDEX probe_points_geom_gix ON probe_points USING gist (geom);
ANALYZE probe_points;
SELECT pg_temp.assert((SELECT count(*) = 9 FROM probe_points
  WHERE ST_Intersects(geom, ST_MakeEnvelope(10,10,12,12,4326))), 'GiST spatial result count');
DO $$
DECLARE plan json;
BEGIN
  EXECUTE 'EXPLAIN (FORMAT JSON, ANALYZE, BUFFERS) SELECT id FROM probe_points
    WHERE ST_Intersects(geom, ST_MakeEnvelope(10,10,12,12,4326))' INTO plan;
  RAISE NOTICE 'GiST observed plan: %', plan;
  PERFORM pg_temp.assert(strpos(plan::text, 'probe_points_geom_gix') > 0 AND
    (strpos(plan::text, 'Index Scan') > 0 OR strpos(plan::text, 'Bitmap') > 0),
    'GiST used by actual planner');
END $$;
SELECT pg_temp.assert(abs(ST_X(g) - 111319.49079327357) < 0.000001 AND
  abs(ST_Y(g) - 111325.1428663851) < 0.000001 AND ST_SRID(g) = 3857,
  'PROJ EPSG 4326 to 3857') FROM (SELECT ST_Transform(ST_SetSRID(ST_Point(1,1),4326),3857) g) q;
SELECT pg_temp.assert(ST_Equals(ST_GeomFromGeoJSON(ST_AsGeoJSON(g)), g),
  'GeoJSON serialization and parsing') FROM (SELECT ST_SetSRID(ST_Point(1,2),4326) g) q;
SELECT pg_temp.assert(length(tile) > 0, 'MVT encoded nonempty tile') FROM (
  SELECT ST_AsMVT(q, 'probe', 4096, 'geom', 'id') tile FROM (
    SELECT 1::bigint id, 'fixture'::text label,
      ST_AsMVTGeom(ST_SetSRID(ST_Point(1,1),3857),
        ST_MakeEnvelope(0,0,10,10,3857),4096,0,true) geom) q) t;
SELECT pg_temp.assert((SELECT count(*) = 1 FROM ST_GDALDrivers()
  WHERE short_name = 'GTiff' AND can_read AND can_write), 'GDAL GTiff read and write driver');
CREATE TEMP TABLE probe_raster AS SELECT ST_AddBand(
  ST_MakeEmptyRaster(2,2,0,2,1,-1,0,0,4326), '8BUI'::text, 7, 0) r;
SELECT pg_temp.assert(ST_Width(r) = 2 AND ST_Height(r) = 2 AND
  ST_Value(r,1,1,1) = 7 AND ST_SRID(r) = 4326, 'raster construction') FROM probe_raster;
SELECT pg_temp.assert(ST_Width(r) = 2 AND ST_Height(r) = 2 AND
  ST_Value(r,1,2,2) = 7 AND ST_SRID(r) = 4326, 'GDAL GTiff raster round trip') FROM (
  SELECT ST_FromGDALRaster(ST_AsGDALRaster(r,'GTiff'),4326) r FROM probe_raster) q;
SELECT pg_temp.assert(topology.CreateTopology('ambisgis_probe_topology',4326) > 0,
  'topology creation');
SELECT pg_temp.assert(topology.ST_AddIsoNode('ambisgis_probe_topology',NULL,
  ST_SetSRID(ST_Point(1,1),4326)) > 0, 'topology node insertion');
SELECT pg_temp.assert((SELECT count(*) = 1 FROM ambisgis_probe_topology.node),
  'topology stored node');
SELECT topology.DropTopology('ambisgis_probe_topology');
SELECT 'AMBISGIS_ASSERT|' || test FROM probe_results ORDER BY test;
SELECT 'AMBISGIS_COUNT|' || count(*) FROM probe_results;
