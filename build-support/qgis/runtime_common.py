#!/usr/bin/env python3
"""Shared assertions for the finite F02-04 synthetic QGIS witness."""
import hashlib
import json
import os
from pathlib import Path

POINTS = ((1, 'alpha', 1.0, 1.0), (2, 'beta', 3.0, 1.0), (3, 'gamma', 2.0, 3.0))
SAMPLES = ((0.5, 3.5, 40), (3.5, 3.5, 90), (0.5, 0.5, 150), (3.5, 0.5, 210))
LAYERS = {'local_points': 'ogr', 'database_points': 'postgres', 'known_raster': 'gdal'}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''): h.update(block)
    return h.hexdigest()


def save(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True); stream.write('\n')


def require(condition, message):
    if not condition: raise AssertionError(message)


def inventory(root):
    root = Path(root).resolve()
    return {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts}


def selected_xml_origin(config, mapped_files):
    """Require one mapped libxml2, exactly the selected QGIS-specific build."""
    require('xml_prefix' in config, 'selected xml_prefix is required')
    root = Path(config['xml_prefix']).resolve()
    expected = (root/'lib/libxml2.so').resolve()
    require(expected.is_relative_to(root), 'selected libxml2 link escapes its retained prefix')
    found = {Path(path).resolve() for path in mapped_files if Path(path).name.startswith('libxml2.so')}
    require(len(found) == 1, 'required libxml2 mapping absent or multiple libxml2 copies loaded')
    require(found == {expected}, 'unselected libxml2 mapping; original native or host fallback is forbidden')
    return str(expected)


def loaded_origins(config, pid=None):
    """Actual mappings, with selected engines constrained to retained prefixes."""
    pid = pid or os.getpid()
    names = set()
    for line in Path(f'/proc/{pid}/maps').read_text().splitlines():
        fields = line.split(maxsplit=5)
        if len(fields) == 6 and fields[5].startswith('/'):
            names.add(fields[5].removesuffix(' (deleted)'))
    roots = [Path(config[k]).resolve() for k in ('qgis_prefix', 'spatial_prefix', 'database_prefix', 'support_prefix')]
    expectations = {'libqgis_core': roots[:1], 'libgdal.so': roots[1:3],
                    'libproj.so': roots[1:3], 'libgeos_c.so': roots[1:3],
                    'libpq.so': roots[1:3], 'libQt5Core.so': roots[3:],
                    'libxml2.so': [Path(config['xml_prefix']).resolve()],
                    'libprovider_postgres.so': [Path(config.get('provider_path', roots[0]/'lib/qgis/plugins')).resolve()]}
    for p in names:
        if Path(p).name.startswith(('libqgis_', 'libprovider_')):
            require(Path(p).resolve().is_relative_to(roots[0]), 'unretained QGIS library/provider mapping')
        if '/PyQt5/' in p:
            require(Path(p).resolve().is_relative_to(roots[3]), 'unretained PyQt binding mapping')
        if '/qgis/_' in p:
            require(Path(p).resolve().is_relative_to(roots[0]), 'unretained QGIS binding mapping')
    selected_xml_origin(config, names)
    selected = {}
    for prefix, allowed in expectations.items():
        found = sorted(p for p in names if Path(p).name.startswith(prefix))
        require(bool(found), 'required runtime mapping absent: ' + prefix)
        require(all(any(Path(p).resolve().is_relative_to(root) for root in allowed) for p in found),
                'unretained engine mapping: ' + prefix)
        selected[prefix] = [{'path': p, 'sha256': sha(p)} for p in found]
    return {'pid': pid, 'executable': str(Path(f'/proc/{pid}/exe').resolve()),
            'selected': selected, 'all_mapped_files': sorted(names),
            'proj_data': os.environ.get('PROJ_DATA'), 'proj_network': os.environ.get('PROJ_NETWORK')}


def check_layers(project):
    result = {}
    require(len(project.mapLayers()) == 3, 'expected exactly three fixture layers')
    for name, provider in LAYERS.items():
        matches = project.mapLayersByName(name)
        require(len(matches) == 1, 'missing or duplicate fixture layer: ' + name)
        layer = matches[0]
        require(layer.isValid() and layer.providerType() == provider, 'invalid fixture provider: ' + name)
        require(layer.crs().authid() == 'EPSG:4326', 'fixture CRS changed: ' + name)
        entry = {'provider': provider, 'crs': layer.crs().authid()}
        if provider in ('ogr', 'postgres'):
            rows = []
            for f in layer.getFeatures():
                point = f.geometry().asPoint()
                rows.append((int(f['id']), str(f['label']), float(point.x()), float(point.y())))
            require(sorted(rows) == list(POINTS), 'fixture attributes/geometries differ: ' + name)
            require(layer.featureCount() == 3, 'wrong feature count: ' + name)
            native_ids = sorted(f.id() for f in layer.getFeatures())
            require(native_ids == [1, 2, 3], 'unexpected native feature IDs: ' + name)
            entry.update(features=sorted(rows), native_feature_ids=native_ids)
        else:
            from qgis.core import QgsPointXY
            require(layer.width() == 16 and layer.height() == 16, 'wrong raster dimensions')
            extent = layer.extent()
            require((extent.xMinimum(), extent.yMinimum(), extent.xMaximum(), extent.yMaximum()) == (0, 0, 4, 4), 'wrong raster extent')
            entry['samples'] = []
            for x, y, expected in SAMPLES:
                value, ok = layer.dataProvider().sample(QgsPointXY(x, y), 1)
                require(ok and value == expected, 'raster sample differs from independently fixed value')
                entry['samples'].append({'point': [x, y], 'expected': expected, 'actual': value})
        result[name] = entry
    return result


def image_witness(image, extent, *, raster=True, local=True, database=True):
    """Spatially placed colors, not a hash or a nonempty-image proxy.

    Raster interiors allow 8 levels for color conversion. Marker search permits
    antialiasing within 24 pixels around each known geometry; a wrong layout or
    missing layer cannot pass merely because another pixel has the right color.
    """
    require(not image.isNull() and image.width() >= 256 and image.height() >= 256, 'invalid rendered image')
    xmin, ymin, xmax, ymax = extent
    require(xmax > xmin and ymax > ymin, 'invalid image extent')
    def pixel(x, y):
        return round((x-xmin)/(xmax-xmin)*(image.width()-1)), round((ymax-y)/(ymax-ymin)*(image.height()-1))
    checks = []
    if raster:
        for x, y, value in SAMPLES:
            px, py = pixel(x, y)
            require(0 <= px < image.width() and 0 <= py < image.height(), 'raster witness outside canvas')
            color = image.pixelColor(px, py)
            rgb = color.getRgb()[:3]
            require(all(abs(v-value) <= 8 for v in rgb), 'raster render value/layout mismatch')
            checks.append({'kind': 'raster', 'xy': [x, y], 'rgb': rgb, 'expected': value})
    for ident, _, x, y in POINTS:
        px, py = pixel(x, y)
        colors = [image.pixelColor(ix, iy).getRgb()[:3]
                  for ix in range(max(0, px-24), min(image.width(), px+25))
                  for iy in range(max(0, py-24), min(image.height(), py+25))]
        for enabled, name, rgb in ((local, 'local', (220, 20, 30)), (database, 'database', (20, 60, 230))):
            if enabled:
                count = sum(all(abs(a-b) <= 20 for a, b in zip(color, rgb)) for color in colors)
                require(count >= 8, name + ' marker missing or misplaced at feature ' + str(ident))
                checks.append({'kind': name, 'feature_id': ident, 'matching_pixels': count})
    return {'width': image.width(), 'height': image.height(), 'extent': list(extent), 'checks': checks}


def provider_origins(config):
    """QGIS_PLUGINPATH controls Python plugins; native providers use this registry."""
    from qgis.core import QgsApplication, QgsProviderRegistry
    prefix = Path(config['qgis_prefix']).resolve()
    expected = Path(config.get('provider_path', prefix/'lib/qgis/plugins')).resolve()
    registry = QgsProviderRegistry.instance()
    actual = Path(registry.libraryDirectory().absolutePath()).resolve()
    require(expected.is_relative_to(prefix), 'native provider path is outside staged QGIS')
    require(actual == expected and Path(QgsApplication.pluginPath()).resolve() == expected,
            'native provider registry is not using the staged plugin directory')
    require(all(registry.providerMetadata(name) is not None for name in ('ogr', 'gdal', 'postgres')),
            'required native provider metadata missing')
    resources = {}
    for name, path in (('master_database', QgsApplication.qgisMasterDatabaseFilePath()),
                       ('srs_database', QgsApplication.srsDatabaseFilePath())):
        path = Path(path).resolve()
        require(path.is_relative_to(prefix) and path.is_file(), 'QGIS resource outside stage: '+name)
        resources[name] = {'path': str(path), 'sha256': sha(path)}
    return {'native_registry_directory': str(actual), 'application_plugin_path': QgsApplication.pluginPath(),
            'discovered_provider_keys': sorted(registry.providerList()),
            'providers_exercised_by_fixture': ['ogr', 'gdal', 'postgres'],
            'optional_python_plugin_path': os.environ.get('QGIS_PLUGINPATH'),
            'core_linked_providers': ['ogr', 'gdal'], 'dynamic_provider': 'postgres', 'resources': resources}


def python_origins(config):
    """Reject host-package fallback for both compiled and pure Python bindings."""
    import sys
    roots = {'qgis': Path(config['qgis_prefix']).resolve(), 'PyQt5': Path(config['support_prefix']).resolve()}
    result = {}
    for name, module in sorted(sys.modules.copy().items()):
        family = name.split('.', 1)[0]
        if family not in roots or not getattr(module, '__file__', None):
            continue
        path = Path(module.__file__).resolve()
        require(path.is_relative_to(roots[family]), 'unretained Python binding module: '+name)
        result[name] = {'path': str(path), 'sha256': sha(path)}
    require('qgis._core' in result and 'PyQt5.QtCore' in result, 'required Python binding origins absent')
    return result
