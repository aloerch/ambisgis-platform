/* Real browser witness. Security stays enabled; no API response is fabricated. */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const config = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const {chromium} = require(config.playwright);
const allowed = new Set([config.origin, new URL(config.geoserverOrigin).origin]);
const manifest = JSON.parse(fs.readFileSync(config.manifest, 'utf8'));
const result = {result_exit_code: 1, phase: config.phase, sandbox_requested: true,
    containment: 'Chromium sandbox enabled; separate from backend ptrace supervisor; page network restricted to exact task origins. This is not host-wide egress proof.',
    requests: [], responses: [], failed: [], external: [], console_errors: [], expected_anonymous_denials: [], page_errors: [], loaded_artifacts: {}, render: []};
let browser;
let page;
let evidenceComplete = false;
let interrupted = false;
process.on('SIGTERM', () => {
    interrupted = true;
    result.error = 'browser coordinator requested termination';
    if (browser) browser.close().catch(error => { result.close_error = String(error); });
});
const pending = [];
function redPixels() {
    return Array.from(document.querySelectorAll('.ol-layer canvas')).map(canvas => {
        const ctx = canvas.getContext('2d');
        const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
        let count = 0;
        for (let i = 0; i < data.length; i += 4) {
            if (data[i] > 170 && data[i + 1] < 70 && data[i + 2] < 70 && data[i + 3] > 100) count++;
        }
        return {width: canvas.width, height: canvas.height, red_pixels: count};
    });
}
async function settle(page, label) {
    await page.waitForFunction(() => {
        try {
            return Array.from(document.querySelectorAll('.ol-layer canvas')).some(canvas => {
                const data = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
                for (let i = 0; i < data.length; i += 4) {
                    if (data[i] > 170 && data[i + 1] < 70 && data[i + 2] < 70 && data[i + 3] > 100) return true;
                }
                return false;
            });
        } catch (_) { return false; }
    }, null, {timeout: 90000});
    await page.waitForTimeout(1000);
    const pixels = await page.evaluate(redPixels);
    if (pixels.reduce((sum, item) => sum + item.red_pixels, 0) < 20) throw Error('map canvas lacks the known red public witness');
    const dom = await page.evaluate(() => ({title: document.title, resourceId: window.__GEONODE_CONFIG__?.resourceId,
        mapContainers: document.querySelectorAll('.ol-viewport').length,
        canvases: document.querySelectorAll('.ol-layer canvas').length,
        buttons: Array.from(document.querySelectorAll('button')).map(button => ({title:button.title, label:button.getAttribute('aria-label'), text:button.textContent.trim()})).slice(0,80),
        text: document.body.innerText.slice(0,12000)}));
    if (String(dom.resourceId) !== String(config.mapId) || dom.mapContainers < 1) throw Error('native map resource was not rendered');
    result.render.push({label, pixels, dom});
    await page.screenshot({path: path.join(config.output, label + '.png')});
}
(async () => {
    try {
        browser = await chromium.launch({headless: true, chromiumSandbox: true, executablePath: config.chromium});
        result.browser_version = browser.version();
        const context = await browser.newContext({viewport: {width: 1100, height: 740}, serviceWorkers: 'block'});
        await context.route('**/*', async route => {
            const request = route.request();
            const url = new URL(request.url());
            if (!allowed.has(url.origin) || !['GET','HEAD','OPTIONS'].includes(request.method())) {
                result.external.push({url:request.url(), method:request.method()});
                return route.abort('blockedbyclient');
            }
            const proxy = url.searchParams.get('url');
            if (proxy && !allowed.has(new URL(proxy).origin)) {
                result.external.push({url:request.url(), reason:'external proxy destination'});
                return route.abort('blockedbyclient');
            }
            result.requests.push({url:request.url(), method:request.method(), type:request.resourceType()});
            return route.continue();
        });
        await context.routeWebSocket('**/*', route => { result.external.push({url:route.url(), reason:'unexpected websocket'}); route.close(); });
        page = await context.newPage();
        page.on('console', msg => {
            if (msg.type() === 'error') {
                const row = {text:msg.text(), url:msg.location().url};
                if (row.url === config.origin + '/api/v2/userinfo/' && row.text === 'Failed to load resource: the server responded with a status of 401 (Unauthorized)') {
                    result.expected_anonymous_denials.push(row);
                } else result.console_errors.push(row);
            }
        });
        page.on('pageerror', error => result.page_errors.push(String(error)));
        page.on('requestfailed', req => result.failed.push({url:req.url(), failure:req.failure()}));
        page.on('response', response => {
            pending.push((async () => {
                const url = new URL(response.url());
                const row = {url:response.url(), status:response.status(), content_type:response.headers()['content-type'] || ''};
                if (response.status() === 200) {
                    const bytes = await response.body();
                    row.bytes = bytes.length; row.sha256 = hash(bytes);
                    if (url.pathname.startsWith('/static/mapstore/')) {
                        const name = decodeURIComponent(url.pathname.slice('/static/mapstore/'.length));
                        if (!Object.hasOwn(manifest, name) || manifest[name] !== row.sha256) throw Error('served artifact differs from staged compiled artifact: ' + name);
                        result.loaded_artifacts[name] = row.sha256;
                    }
                    if (decodeURIComponent(response.url()).toLowerCase().includes('getmap')) {
                        if (!row.content_type.includes('image/png') || bytes.length < 100) throw Error('real WMS request did not return PNG');
                        const name = 'wms-' + row.sha256 + '.png';
                        if (!fs.existsSync(path.join(config.output,name))) fs.writeFileSync(path.join(config.output,name),bytes);
                        row.retained_body = name;
                    }
                }
                result.responses.push(row);
            })().catch(error => result.page_errors.push(String(error))));
        });
        await page.goto(config.origin + config.route, {waitUntil:'domcontentloaded', timeout:45000});
        await settle(page, 'initial');
        await Promise.all(pending);
        function bboxSpan(url) {
            const parsed = new URL(url);
            const params = parsed.searchParams;
            const value = params.get('BBOX') || params.get('bbox');
            if (!value) return null;
            const coords = value.split(',').map(Number);
            return coords.length === 4 && coords.every(Number.isFinite) ? Math.abs(coords[2] - coords[0]) : null;
        }
        const initialWms = result.responses.filter(row => row.retained_body).map(row => row.url);
        const initialSpan = initialWms.map(bboxSpan).filter(value => value > 0);
        if (!initialSpan.length) throw Error('initial WMS request has no measurable BBOX');
        const viewport = page.locator('.ol-viewport').first();
        const box = await viewport.boundingBox();
        await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
        await page.mouse.wheel(0, -400);
        await settle(page, 'zoom');
        await Promise.all(pending);
        const afterWms = result.responses.filter(row => row.retained_body).map(row => row.url);
        const zoomSpans = afterWms.filter(url => !initialWms.includes(url)).map(bboxSpan).filter(value => value > 0);
        if (!zoomSpans.some(span => span < Math.min(...initialSpan))) throw Error('zoom did not shrink the real WMS BBOX');
        result.interaction = {kind:'wheel zoom', initial_bbox_spans:initialSpan, zoom_bbox_spans:zoomSpans, smaller_bbox:true};
        await page.reload({waitUntil:'domcontentloaded',timeout:45000});
        await settle(page, 'reload');
        await Promise.all(pending);
        if (!Object.hasOwn(result.loaded_artifacts,'dist/js/gn-map.js')) throw Error('fresh compiled gn-map entry was not received');
        if (!Object.keys(result.loaded_artifacts).some(name => /\.js$/.test(name) && name !== 'dist/js/gn-map.js')) throw Error('no loaded compiled chunk was verified');
        if (!result.responses.some(row => row.status === 200 && row.url.includes('/api/v2/') && row.content_type.includes('json'))) throw Error('no real backend viewer metadata/configuration response');
        if (result.external.length || result.failed.length || result.console_errors.length || result.page_errors.length || result.responses.some(row => row.status >= 400 && !(row.status === 401 && row.url === config.origin + '/api/v2/userinfo/'))) {
            throw Error('network, missing resource, or blocking browser error');
        }
        evidenceComplete = true;
    } catch (error) {
        result.error = String(error);
        if (page && !page.isClosed()) {
            try { await page.screenshot({path:path.join(config.output,'failure.png')}); } catch (_) {}
            try { result.failure_pixels = await page.evaluate(redPixels); } catch (pixelError) { result.pixel_error=String(pixelError); }
        }
    }
    finally {
        // Close the browser first, then drain every observed response. A late
        // response/error cannot appear after this final acceptance decision.
        if (browser) {try {await browser.close(); result.browser_closed=true;} catch(error) {result.close_error=String(error);}}
        await Promise.allSettled(pending);
        const lateFailure = result.external.length || result.failed.length || result.console_errors.length ||
            result.page_errors.length || result.responses.some(row => row.status >= 400 && !(row.status === 401 && row.url === config.origin + '/api/v2/userinfo/')) || result.close_error;
        result.result_exit_code = evidenceComplete && !interrupted && result.browser_closed && !lateFailure ? 0 : 1;
        result.evidence_files = Object.fromEntries(fs.readdirSync(config.output).filter(name => name.endsWith('.png'))
            .map(name => [name,hash(fs.readFileSync(path.join(config.output,name)))]));
        fs.writeFileSync(path.join(config.output,'result.json'), JSON.stringify(result,null,2)+'\n');
        console.log(JSON.stringify({phase:config.phase,result_exit_code:result.result_exit_code,error:result.error,
            loaded_artifacts:Object.keys(result.loaded_artifacts).length,render_steps:result.render.length}));
        process.exitCode=result.result_exit_code;
    }
})();
