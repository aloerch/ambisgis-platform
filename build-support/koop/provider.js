'use strict';
// Finite private evaluation boundary around the unchanged Koop source codec.
// Native provider owns predicates and current catalog permission checks.
const fs = require('fs');
const path = require('path');
const http = require('http');
const crypto = require('crypto');
const config = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const rootRequire = require('module').createRequire(path.join(config.app, 'package.json'));
const Koop = rootRequire('@koopjs/koop-core');
const logger = { info() {}, warn() {}, debug() {}, error() {}, silly() {}, verbose() {} };
const koop = new Koop({ logger, disableCors: true, disableCompression: true,
  bodyParserLimit: '32kb', geoservicesDefaults: { maxRecordCount: 1000 } });
if (koop.config.disableCors !== true || koop.config.disableCompression !== true ||
    koop.config.bodyParserLimit !== '32kb' || koop.config.logger !== logger ||
    process.env.OBJECTID_FEATURE_HASH !== 'javascript') throw new Error('CONFIGURATION_MISMATCH');
const stats = { authorize: 0, getData: 0, cacheRetrieve: 0, cacheInsert: 0, rawResponses: 0 };
function persist() { fs.writeFileSync(path.join(config.output, 'koop-stats.json'), JSON.stringify(stats, null, 2)); }
class NoCache {
  static type = 'cache';
  static version = 'private-spike-1';
  async retrieve() { stats.cacheRetrieve++; return undefined; }
  async insert() { stats.cacheInsert++; throw new Error('CACHE_FORBIDDEN'); }
}
koop.register(NoCache);
function backend(endpoint, req, query) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify({ resource: req.spike.resource, ...(query === undefined ? {} : { query }) });
    const request = http.request({ host: '127.0.0.1', port: config.backend_port, path: endpoint,
      method: 'POST', timeout: 5000, headers: { 'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(body), 'X-Spike-Key': config.backend_key,
        Authorization: req.headers.authorization || '' } }, response => {
      let bytes = 0; const chunks = [];
      response.on('data', chunk => { bytes += chunk.length; if (bytes > 2 * 1024 * 1024) response.destroy(); else chunks.push(chunk); });
      response.on('end', () => {
        try {
          const value = JSON.parse(Buffer.concat(chunks));
          if (response.statusCode !== 200) {
            const error = new Error(value.error?.code || 'BACKEND_UNAVAILABLE');
            error.code = response.statusCode; reject(error);
          } else resolve(value);
        } catch (_) { reject(Object.assign(new Error('BACKEND_UNAVAILABLE'), { code: 503 })); }
      });
      response.on('error', () => reject(Object.assign(new Error('BACKEND_UNAVAILABLE'), { code: 503 })));
    });
    request.on('timeout', () => request.destroy());
    request.on('error', () => reject(Object.assign(new Error('BACKEND_UNAVAILABLE'), { code: 503 })));
    request.end(body);
  });
}
class Model {
  async authorize(req) { stats.authorize++; await backend('/authorize', req); }
  async getData(req) {
    stats.getData++;
    const data = await backend(req.spike.metadata ? '/metadata' : '/c1', req, req.spike.params);
    req.spike.nativeMode = data.spikeNativeMode;
    req.spike.emptyExtent = data.spikeNativeMode === 'extent' && data.extent === null;
    delete data.spikeNativeMode;
    return data;
  }
}
koop.register({ type: 'provider', name: 'owned', version: 'private-spike-1', Model });

function fail(res, status, message) {
  const payload = JSON.stringify({ error: { code: status, message, details: [] } });
  res.writeHead(status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store', 'Content-Length': Buffer.byteLength(payload) });
  res.end(payload); persist();
}
let counter = 0;
const server = http.createServer({ maxHeaderSize: 8192 }, (req, res) => {
  if (!['GET', 'POST'].includes(req.method)) return fail(res, 405, 'UNSUPPORTED_CAPABILITY');
  if (req.url.length > 32768 || req.headers['content-encoding'] || req.headers['transfer-encoding']) return fail(res, 413, 'LIMIT_EXCEEDED');
  if (Object.keys(req.headers).some(name => name.startsWith('x-ambisgis-') || name.startsWith('x-spike-'))) return fail(res, 403, 'NOT_FOUND_OR_FORBIDDEN');
  const auth = req.headers.authorization || '';
  if ((auth && !/^Bearer [A-Za-z0-9._~-]{20,512}$/.test(auth)) ||
      req.rawHeaders.filter((_, i) => i % 2 === 0).filter(name => name.toLowerCase() === 'authorization').length > 1) return fail(res, 403, 'NOT_FOUND_OR_FORBIDDEN');
  let url;
  try { url = new URL(req.url, 'http://127.0.0.1'); } catch (_) { return fail(res, 400, 'INVALID_REQUEST'); }
  const match = /^\/owned\/rest\/services\/([a-z_]{1,64})\/FeatureServer\/0(\/query)?$/.exec(url.pathname);
  if (!match) return fail(res, 404, 'UNSUPPORTED_CAPABILITY');
  if (req.method === 'POST' && req.headers['content-type'] !== 'application/x-www-form-urlencoded') return fail(res, 415, 'UNSUPPORTED_CAPABILITY');
  if (Number(req.headers['content-length'] || 0) > 32768) return fail(res, 413, 'LIMIT_EXCEEDED');
  const bodyChunks = []; let bodyBytes = 0; let rejected = false;
  req.setTimeout(5000, () => req.destroy());
  req.on('data', chunk => {
    bodyBytes += chunk.length;
    if (bodyBytes > 32768 && !rejected) { rejected = true; fail(res, 413, 'LIMIT_EXCEEDED'); }
    if (!rejected) bodyChunks.push(chunk);
  });
  req.on('end', () => {
    if (rejected) return;
    let body;
    try { body = new TextDecoder('utf-8', { fatal: true }).decode(Buffer.concat(bodyChunks)); }
    catch (_) { return fail(res, 400, 'INVALID_REQUEST'); }
    if (req.method === 'GET' && body) return fail(res, 400, 'INVALID_REQUEST');
    const params = Object.create(null);
    let pairs;
    try {
      pairs = [url.search.slice(1), body].flatMap(text => text ? text.split('&').map(item => {
        const index = item.indexOf('=');
        const pair = index < 0 ? [item, ''] : [item.slice(0, index), item.slice(index + 1)];
        return pair.map(value => decodeURIComponent(value.replace(/\+/g, ' ')));
      }) : []);
    } catch (_) { return fail(res, 400, 'INVALID_REQUEST'); }
    for (const [key, value] of pairs) {
      if (Object.hasOwn(params, key) || ['__proto__', 'constructor', 'prototype'].includes(key)) return fail(res, 400, 'INVALID_REQUEST');
      params[key] = value;
    }
    if (!match[2] && (Object.keys(params).some(key => key !== 'f') || (params.f && params.f !== 'json'))) return fail(res, 400, 'UNSUPPORTED_CAPABILITY');
    req.spike = { resource: match[1], params, metadata: !match[2] };
    // Raw incoming stream has been bounded and consumed. Supply only the exact
    // validated form values to Express/Koop, preserving GET/POST equivalence.
    req.body = params;
    req._body = true;
    delete req.headers['content-type'];
    delete req.headers['content-length'];
    req.url = url.pathname; // avoid duplicate merge; parameters are now req.body.
    const chunks = []; const end = res.end.bind(res); let responseBytes = 0; let overflow = false;
    function append(chunk) {
      if (!chunk) return;
      const value = Buffer.from(chunk); responseBytes += value.length;
      if (responseBytes > 2 * 1024 * 1024) { overflow = true; chunks.length = 0; }
      if (!overflow) chunks.push(value);
    }
    res.write = chunk => { append(chunk); return !overflow; };
    res.end = chunk => {
      append(chunk);
      const raw = Buffer.concat(chunks);
      let output = raw;
      const id = String(++counter).padStart(5, '0');
      fs.writeFileSync(path.join(config.output, 'raw-' + id + '.json'), raw);
      stats.rawResponses++;
      try {
        if (overflow) throw new Error('LIMIT_EXCEEDED');
        let value = JSON.parse(raw);
        if (!value.error && req.spike.metadata) {
          // Exact metadata projection, not a replacement feature encoder.
          value = Object.fromEntries(['id', 'name', 'type', 'geometryType', 'objectIdField', 'globalIdField', 'fields']
            .filter(key => Object.hasOwn(value, key)).map(key => [key, value[key]]));
          value.capabilities = 'Query'; value.supportedQueryFormats = 'JSON'; value.supportsStatistics = false;
          value.supportsPagination = true;
          value.advancedQueryCapabilities = { supportsPagination: true, supportsOrderBy: true,
            supportsStatistics: false, supportsDistinct: false, supportsReturningQueryExtent: true };
          value.maxRecordCount = 1000; value.hasZ = false; value.hasM = false;
          output = Buffer.from(JSON.stringify(value));
        } else if (!value.error && req.spike.emptyExtent) {
          value.extent = null; output = Buffer.from(JSON.stringify(value));
        }
      } catch (_) {
        res.statusCode = overflow ? 413 : 503;
        output = Buffer.from(JSON.stringify({ error: { code: res.statusCode, message: overflow ? 'LIMIT_EXCEEDED' : 'BACKEND_UNAVAILABLE', details: [] } }));
      }
      if (output.length > 2 * 1024 * 1024) {
        res.statusCode = 413;
        output = Buffer.from(JSON.stringify({ error: { code: 413, message: 'LIMIT_EXCEEDED', details: [] } }));
      }
      fs.writeFileSync(path.join(config.output, 'projection-' + id + '.json'), JSON.stringify({
        raw_sha256: crypto.createHash('sha256').update(raw).digest('hex'),
        projected_sha256: crypto.createHash('sha256').update(output).digest('hex'),
        changed: !raw.equals(output), metadata: req.spike.metadata, empty_extent: !!req.spike.emptyExtent,
        raw_overflow: overflow, observed_raw_bytes: responseBytes }));
      res.removeHeader('Content-Length'); res.removeHeader('ETag');
      res.setHeader('Cache-Control', 'no-store'); res.setHeader('Content-Length', output.length);
      persist(); return end(output);
    };
    koop.server(req, res);
  });
});
server.headersTimeout = 5000; server.requestTimeout = 8000; server.maxConnections = 8;
server.listen(config.koop_port, '127.0.0.1', () => {
  persist(); console.log(JSON.stringify({ event: 'koop_listening', port: config.koop_port,
    core_version: koop.version, cache: 'explicit no-cache', config_empty: true }));
});
