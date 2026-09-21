// Independently authored bounded IFC API/geometry probe, GPL-3.0-or-later.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
(async () => {
  const diagnostics = [];
  const originalLog = console.log;
  console.log = (...args) => { diagnostics.push(args.map(String).join(' ')); originalLog(...args); };
  const packageRoot = path.resolve(process.argv[2]);
  const fixture = fs.readFileSync(process.argv[3]);
  const webifc = require(path.join(packageRoot, 'web-ifc-api-node.js'));
  const api = new webifc.IfcAPI();
  await api.Init();
  assert.equal(api.GetVersion(), '0.0.50');
  const model = api.OpenModel(fixture, {COORDINATE_TO_ORIGIN: false});
  assert.equal(api.IsModelOpen(model), true);
  assert.equal(api.GetModelSchema(model), 'IFC2X3');
  assert.equal(api.GetLineIDsWithType(model, webifc.IFCWALLSTANDARDCASE).size(), 1);
  const meshes = api.LoadAllGeometry(model);
  assert.equal(meshes.size(), 1);
  const mesh = meshes.get(0);
  assert.equal(mesh.expressID, 25);
  assert.equal(mesh.geometries.size(), 1);
  const geom = api.GetGeometry(model, mesh.geometries.get(0).geometryExpressID);
  const vertices = api.GetVertexArray(geom.GetVertexData(), geom.GetVertexDataSize());
  const indices = api.GetIndexArray(geom.GetIndexData(), geom.GetIndexDataSize());
  assert.equal(indices.length, 36);
  const bounds = [0, 1, 2].map(axis => {
    const values = Array.from({length:vertices.length/6}, (_, i) => vertices[i*6+axis]);
    assert(values.every(Number.isFinite));
    return [Math.min(...values), Math.max(...values)];
  });
  assert.deepEqual(bounds.map(([lo, hi]) => hi-lo).sort((a,b) => a-b), [2,3,4]);
  const saved = api.SaveModel(model);
  api.CloseModel(model);
  assert.equal(api.IsModelOpen(model), false);
  const reopened = api.OpenModel(saved);
  assert.equal(api.LoadAllGeometry(reopened).size(), 1);
  api.CloseModel(reopened);
  assert(!diagnostics.some(line => /\[error\]/i.test(line)), 'IFC engine reported an error');
  const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
  console.log(JSON.stringify({status:'passed', version:api.GetVersion(), fixture_sha256:hash(fixture),
    wasm_sha256:hash(fs.readFileSync(path.join(packageRoot,'web-ifc-node.wasm'))),
    meshes:meshes.size(), triangles:indices.length/3, bounds, save_reopen:true,
    bindings:Object.keys(api.wasmModule).sort()}, null, 2));
})().catch(error => { console.error(error); process.exitCode = 1; });
