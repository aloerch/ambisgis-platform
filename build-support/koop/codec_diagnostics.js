'use strict';
// Real unchanged codec calls for known control-flag hazards. These are component
// diagnostics, separate from the real catalog/HTTP/PostGIS acceptance journey.
const fs = require('fs');
const path = require('path');
const [app, output] = process.argv.slice(2);
const { queryJson } = require(path.join(app, 'packages/featureserver/src/query/query-json.js'));
const base = { type: 'FeatureCollection', metadata: { idField: 'object_id',
  fields: [{ name: 'object_id', type: 'Integer' }, { name: 'name', type: 'String' }] },
features: [1, 2].map(object_id => ({ type: 'Feature', properties: { object_id, name: 'row' + object_id },
  geometry: { type: 'Point', coordinates: [object_id, object_id] } })) };
const cases = {};
for (const [name, flags] of [['absent', undefined], ['false_where', { where: false }], ['all_true', { all: true }]]) {
  const data = JSON.parse(JSON.stringify(base));
  if (flags) data.filtersApplied = flags;
  cases[name] = queryJson(data, { where: 'object_id = 999', f: 'json' });
}
const report = { scope: 'Actual codec component diagnostics, not independent authorization tests', cases,
  observed_false_flag_removes_where: cases.absent.features.length === 0 && cases.false_where.features.length === 2,
  observed_all_flag_skips_conversion: cases.all_true.features.length === 2 && !!cases.all_true.features[0].properties && !cases.all_true.features[0].attributes };
fs.writeFileSync(output, JSON.stringify(report, null, 2));
if (!report.observed_false_flag_removes_where || !report.observed_all_flag_skips_conversion) process.exitCode = 1;
