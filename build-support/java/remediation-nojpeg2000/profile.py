#!/usr/bin/env python3
"""Apply the explicit NO-JPEG2000 consumer policy to the retained MapFish source.

Called only by the successor candidate; prior source trees/recipes stay intact.
"""
from pathlib import Path
import hashlib

BASE = Path(__file__).resolve().parent
MAPFISH = 'mapfish-print-v2-da1f37cfc0d7a235cb2c0ec5677010495d9f664b'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def prepare(source):
    root = Path(source) / MAPFISH / 'src/main/java/org/mapfish/print'
    expected = {'PDFUtils.java': '0f88cbe4981b5adec6256dcbbce5253846db5d72eeeff12fdd419a447d539a76', 'MapPrinter.java': 'c826fc6c9d58bf021e67c7f51e7cc076276cf8a7ed4e2934f6913fb414743547', 'servlet/MapPrinterServlet.java': '06527fdc1fd1c51efd899804755458177d7e9eb012543690a1a98d3dd7853b2a'}
    expected['config/layout/ImageBlock.java'] = '19027678b29bcba0f294f41dbe70d63606ba365e9c8391e388774b36f38d6a29'
    expected['PDFCustomBlocks.java'] = 'b67fe50f996530a7c7de1c03a2f2a5efac1ae6d292e468e9a0099b1ad27ab015'
    expected['output/AbstractOutputFormat.java'] = '48efcb7327a7b9f03ecf065e719213b6105ceb0c72e4cb8f5184b165634b8229'
    expected['map/renderers/PDFTileRenderer.java'] = '90a10e61590ec6aca8597043f37b2ab20d0d3672292fa80fd3ac641a24fdfab0'
    for relative, expected_sha in expected.items():
        path = root / relative
        if path.is_symlink() or sha(path.read_bytes()) != expected_sha:
            raise ValueError("NO-JPEG2000 requires exact retained source: " + relative)
    changes = []

    def patch(relative, replacements):
        path = root / relative
        before = path.read_bytes()
        text = before.decode()
        for old, new, count in replacements:
            if text.count(old) != count:
                raise ValueError('NO-JPEG2000 patch anchor mismatch: ' + str(path))
            text = text.replace(old, new)
        after = text.encode()
        path.write_bytes(after)
        changes.append({'path': str(path.relative_to(source)),
                        'before_sha256': sha(before), 'after_sha256': sha(after)})

    patch('PDFUtils.java', [(('return Image.getInstance(' + arg + ');'),
                           ('return Jpeg2000Policy.load(' + arg + ');'), 1)
                           for arg in ['uriAsFile.toURI().toURL()', 'uri.toString()',
                                       'new File(path).toURI().toURL()', 'image', 'data']])
    patch('config/layout/ImageBlock.java', [('url.getPath().endsWith(".svg")', '(url.getPath() != null && url.getPath().endsWith(".svg"))', 1)])
    patch('MapPrinter.java', [
        ('            OutputFormat output = this.outputFactory.create(config, jsonSpec);',
         '            Jpeg2000Policy.checkOutput(jsonSpec.optString("outputFormat", "pdf"));\n'
         '            OutputFormat output = this.outputFactory.create(config, jsonSpec);', 1),
        ('    public OutputFormat getOutputFormat(PJsonObject jsonSpec) {',
         '    public OutputFormat getOutputFormat(PJsonObject jsonSpec) {\n'
         '        Jpeg2000Policy.checkOutput(jsonSpec.optString("outputFormat", "pdf"));', 1)])
    # Runtime exceptions must not leave the generated private temp file behind.
    # This is also needed when an image renderer wraps the intentional refusal.
    patch('servlet/MapPrinterServlet.java', [
        ('    protected void error(HttpServletResponse httpServletResponse, Throwable e) {',
         '    protected void error(HttpServletResponse httpServletResponse, Throwable e) {\n'
         '        if (org.mapfish.print.Jpeg2000Policy.isUnsupported(e)) {\n'
         '            error(httpServletResponse, org.mapfish.print.Jpeg2000Policy.MESSAGE, 415);\n'
         '            return;\n'
         '        }\n'
         '        if (org.mapfish.print.Jpeg2000Policy.isLimit(e)) {\n'
         '            error(httpServletResponse, org.mapfish.print.Jpeg2000Policy.LIMIT_MESSAGE, 413);\n'
         '            return;\n'
         '        }', 1),
        ('            } catch (InterruptedException e) {\n                deleteFile(tempFileMetadata.tempFile);\n                throw e;',
         '            } catch (InterruptedException e) {\n                deleteFile(tempFileMetadata.tempFile);\n                throw e;\n'
         '            } catch (RuntimeException e) {\n'
         '                deleteFile(tempFileMetadata.tempFile);\n'
         '                throw e;', 1),
        ('        } finally {\n            deleteFile(tempFileMetadata.tempFile);\n        }',
         '        } finally {\n            if (tempFileMetadata != null) deleteFile(tempFileMetadata.tempFile);\n        }', 1)])
    patch('PDFCustomBlocks.java', [
        ('                    PdfReader reader = new PdfReader(backgroundPdf);',
         '                    PdfReader reader = Jpeg2000Policy.loadPdf(backgroundPdf);', 1),
        ('    public void addError(Exception e) {\n        errors.add(e);',
         '    private volatile RuntimeException unsupportedImageFailure;\n\n'
         '    public void requireSupportedImages() {\n'
         '        if (unsupportedImageFailure != null) throw unsupportedImageFailure;\n'
         '    }\n\n'
         '    public void addError(Exception e) {\n'
         '        if (Jpeg2000Policy.isUnsupported(e)) {\n'
         '            unsupportedImageFailure = new Jpeg2000Policy.UnsupportedFormat();\n'
         '            return;\n'
         '        }\n'
         '        if (Jpeg2000Policy.isLimit(e)) {\n'
         '            unsupportedImageFailure = new Jpeg2000Policy.InputLimit();\n'
         '            return;\n'
         '        }\n'
         '        errors.add(e);', 1)])
    patch('output/AbstractOutputFormat.java', [
        ('        layout.render(params.jsonSpec, context);\n\n'
         '        doc.close();\n        writer.close();\n        context.getCustomBlocks().closeReaders();\n\n'
         '        return context;',
         '        Throwable failure = null;\n'
         '        try {\n'
         '            layout.render(params.jsonSpec, context);\n'
         '            context.getCustomBlocks().requireSupportedImages();\n'
         '            doc.close();\n'
         '            writer.close();\n'
         '            context.getCustomBlocks().closeReaders();\n'
         '            // Final-page header/footer rendering occurs during doc.close().\n'
         '            context.getCustomBlocks().requireSupportedImages();\n'
         '            return context;\n'
         '        } catch (RuntimeException | Error e) {\n'
         '            failure = e;\n'
         '            throw e;\n'
         '        } finally {\n'
         '            try {\n'
         '                try { doc.close(); }\n'
         '                finally {\n'
         '                    try { writer.close(); }\n'
         '                    finally { context.getCustomBlocks().closeReaders(); }\n'
         '                }\n'
         '            } catch (RuntimeException | Error closeFailure) {\n'
         '                if (failure != null) failure.addSuppressed(closeFailure);\n'
         '                else throw closeFailure;\n'
         '            }\n'
         '        }', 1)])
    patch('map/renderers/PDFTileRenderer.java', [
        ('                URLConnection connection = uri.toURL().openConnection();',
         '                URLConnection connection = uri.toURL().openConnection();\n'
         '                connection.setConnectTimeout(org.mapfish.print.Jpeg2000Policy.URL_TIMEOUT_MILLIS);\n'
         '                connection.setReadTimeout(org.mapfish.print.Jpeg2000Policy.URL_TIMEOUT_MILLIS);\n'
         '                if (connection.getContentLengthLong() > org.mapfish.print.Jpeg2000Policy.MAX_IMAGE_BYTES)\n'
         '                    throw new org.mapfish.print.Jpeg2000Policy.InputLimit();', 1),
        ('                    PdfReader reader = new PdfReader(in);',
         '                    PdfReader reader = new PdfReader(org.mapfish.print.Jpeg2000Policy.readBounded(in));\n'
         '                    try { org.mapfish.print.Jpeg2000Policy.checkPdf(reader); }\n'
         '                    catch (RuntimeException failure) { reader.close(); throw failure; }', 1)])
    path = root / 'Jpeg2000Policy.java'
    if path.exists():
        raise ValueError('NO-JPEG2000 source already present')
    data = (BASE / 'Jpeg2000Policy.java').read_bytes()
    path.write_bytes(data)
    changes.append({'path': str(path.relative_to(source)), 'before_sha256': None,
                    'after_sha256': sha(data), 'origin': 'new AmbisGIS Apache-2.0 source'})
    return {'profile': 'NO-JPEG2000', 'changes': changes,
            'recipe': {'path': str(Path(__file__).resolve()),
                       'sha256': sha(Path(__file__).read_bytes())},
            'policy_source': {'path': str(BASE / 'Jpeg2000Policy.java'), 'sha256': sha(data)}}


def scan_war(war_path):
    """Inspect real bytes, including nested archives, SPIs and native payloads.

    This proves absence of known blocked definitions and fingerprints, not legal
    clearance of arbitrary rewritten code. Selected source accounting is separate.
    OpenPDF JPX embedding/PDFBox's optional decoder selector are retained callers;
    MapFish's source-owned policy guards must be packaged and exercised separately.
    """
    import io
    import zipfile
    baseline = Path('/home/revelberry/Projects/AmbisGIS/build-worktrees/java-gmt-remediation/aggregate-02/work/source/geoserver/src/web/app/target/geoserver.war')
    baseline_digest = 'e291629c38cab29eed207d1f88b2cbb747c8ca418c4737f10e5324ebc0aae044'
    if sha(baseline.read_bytes()) != baseline_digest:
        raise ValueError('parent WAR integrity changed')
    prefixes = ('jj2000/', 'com/sun/media/imageio/plugins/jpeg2000/',
                'com/sun/media/imageioimpl/plugins/jpeg2000/')
    fingerprints = set()
    with zipfile.ZipFile(baseline) as parent:
        with zipfile.ZipFile(io.BytesIO(parent.read('WEB-INF/lib/jai_imageio-1.1.jar'))) as original:
            for name in original.namelist():
                if name.startswith(prefixes) and name.endswith('.class'):
                    fingerprints.add(sha(original.read(name)))
    found, providers, native, indirect = [], [], [], []
    seen_classes = set()
    count = 0

    def inspect(data, label, depth=0):
        nonlocal count
        if depth > 8:
            raise ValueError('nested archive exceeds scan bound')
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for name in archive.namelist():
                if name.endswith('/'):
                    continue
                payload = archive.read(name)
                count += 1
                lower = name.lower()
                path = label + '!/' + name
                if lower.endswith(('.jar', '.zip')) or payload.startswith(b'PK\x03\x04'):
                    inspect(payload, path, depth + 1)
                if sha(payload) in fingerprints:
                    found.append(path)
                if name.endswith('.class') or payload.startswith(b'\xca\xfe\xba\xbe'):
                    seen_classes.add(name)
                    if (any(prefix in name for prefix in prefixes)
                            or sha(payload) in fingerprints
                            or b'jj2000/' in payload or b'jj2000.' in payload
                            or b'com/sun/media/imageioimpl/plugins/jpeg2000/' in payload
                            or b'com.sun.media.imageioimpl.plugins.jpeg2000.' in payload):
                        found.append(path)
                    if any(word in payload.lower() for word in (b'jpeg2000', b'jp2k', b'jpxdecode', b'openjpeg')):
                        indirect.append({'path': path, 'sha256': sha(payload)})
                if 'META-INF/services/' in name:
                    providers.append({'path': path, 'sha256': sha(payload),
                                      'registrations': [line for line in payload.decode(errors='replace').splitlines()
                                                        if line.strip() and not line.lstrip().startswith('#')]})
                    if any(word in payload.lower() for word in (b'jpeg2000', b'jj2000', b'jp2k', b'openjpeg', b'kakadu')):
                        found.append(path)
                if (lower.endswith(('.so', '.dll', '.dylib', '.jnilib')) or '.so.' in lower
                        or payload.startswith((b'\x7fELF',b'MZ',b'\xcf\xfa\xed\xfe',b'\xfe\xed\xfa\xcf'))):
                    native.append({'path': path, 'sha256': sha(payload)})
                    if any(word in lower.encode() or word in payload.lower()
                           for word in (b'openjp', b'kakadu', b'clib_jiio', b'jj2000')):
                        found.append(path)
    war_bytes = Path(war_path).read_bytes()
    inspect(war_bytes, str(war_path))
    if found:
        raise ValueError('NO-JPEG2000 blocked definition/provider/native fallback: ' + ', '.join(found[:8]))
    required = ('com/sun/media/imageio/plugins/tiff/TIFFDirectory.class',
                'com/sun/media/imageioimpl/plugins/tiff/TIFFImageReader.class',
                'com/sun/media/imageioimpl/plugins/tiff/TIFFImageWriter.class',
                'org/eclipse/imagen/ImageN.class',
                'it/geosolutions/imageioimpl/plugins/tiff/TIFFImageReader.class',
                'org/mapfish/print/Jpeg2000Policy.class',
                'org/mapfish/print/Jpeg2000Policy$UnsupportedFormat.class',
                'org/geotools/gce/imagemosaic/ImageMosaicReader.class')
    if not set(required).issubset(seen_classes):
        raise ValueError('NO-JPEG2000 required preserved/guard classes absent: ' + str(sorted(set(required)-seen_classes)))
    return {'profile': 'NO-JPEG2000', 'war_path': str(war_path), 'war_sha256': sha(war_bytes),
            'parent_war_sha256': baseline_digest, 'blocked_parent_class_fingerprints': len(fingerprints),
            'members_scanned': count, 'known_blocked_matches': [], 'service_providers': providers,
            'native_members': native, 'remaining_indirect_references': indirect,
            'required_preserved_and_guard_definitions': list(required),
            'scope': 'This Java/server WAR only; OpenPDF/PDFBox indirect JPEG2000 callers require tested policy refusal. Source accounting and other product profiles remain separate.'}


def inspect_artifacts(build, jar_entries, class_origins, libraries):
    return scan_war(Path(build) / 'work/source/geoserver/src/web/app/target/geoserver.war')
