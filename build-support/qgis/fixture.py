#!/usr/bin/env python3
"""Generate fixed GeoJSON/GeoTIFF and a staged-PyQGIS desktop/server project."""
import ctypes as C
import json
import os
from pathlib import Path
import sys

from runtime_common import POINTS, check_layers, loaded_origins, provider_origins, python_origins, require, save, sha


def make_data(output, gdal_library):
    output = Path(output)
    vector = {'type': 'FeatureCollection', 'name': 'local_points', 'features': [
        {'type': 'Feature', 'id': ident, 'properties': {'id': ident, 'label': label},
         'geometry': {'type': 'Point', 'coordinates': [x, y]}} for ident, label, x, y in POINTS]}
    save(output / 'points.geojson', vector)
    lib = C.CDLL(str(gdal_library))
    def api(name, result, args):
        f = getattr(lib, name); f.restype = result; f.argtypes = args; return f
    ptr, string, integer = C.c_void_p, C.c_char_p, C.c_int
    api('GDALAllRegister', None, [])()
    driver = api('GDALGetDriverByName', ptr, [string])(b'GTiff')
    require(driver, 'retained GDAL has no GTiff driver')
    dataset = api('GDALCreate', ptr, [ptr,string,integer,integer,integer,integer,C.POINTER(string)])(
        driver, os.fsencode(output / 'known.tif'), 16, 16, 1, 1, None)
    require(dataset, 'GeoTIFF creation failed')
    try:
        transform = (C.c_double * 6)(0, .25, 0, 4, 0, -.25)
        require(api('GDALSetGeoTransform', integer, [ptr,C.POINTER(C.c_double)])(dataset,transform) == 0, 'geotransform failed')
        srs = api('OSRNewSpatialReference', ptr, [string])(None)
        require(srs, 'SRS allocation failed')
        wkt = string()
        try:
            require(api('OSRImportFromEPSG', integer, [ptr,integer])(srs,4326) == 0, 'EPSG resource unavailable')
            require(api('OSRExportToWkt', integer, [ptr,C.POINTER(string)])(srs,C.byref(wkt)) == 0, 'WKT failed')
            require(api('GDALSetProjection', integer, [ptr,string])(dataset,wkt) == 0, 'projection failed')
        finally:
            if wkt: api('VSIFree',None,[ptr])(C.cast(wkt,ptr))
            api('OSRDestroySpatialReference',None,[ptr])(srs)
        values = (C.c_ubyte * 256)(*(40 if row<8 and col<8 else 90 if row<8 else 150 if col<8 else 210
                                              for row in range(16) for col in range(16)))
        band = api('GDALGetRasterBand',ptr,[ptr,integer])(dataset,1)
        require(api('GDALRasterIO', integer, [ptr,integer,integer,integer,integer,integer,ptr,integer,integer,integer,integer,integer])(
            band,1,0,0,16,16,C.cast(values,ptr),16,16,1,0,0) == 0, 'raster values write failed')
    finally:
        require(api('GDALClose',integer,[ptr])(dataset) == 0, 'GeoTIFF flush/close failed')
    return {p.name: sha(p) for p in (output/'points.geojson', output/'known.tif')}


def generate(config):
    from qgis.core import (Qgis, QgsApplication, QgsContrastEnhancement, QgsCoordinateReferenceSystem,
        QgsCoordinateTransform, QgsDataSourceUri, QgsGeometry, QgsMarkerSymbol, QgsPointXY,
        QgsProject, QgsRasterLayer, QgsRectangle, QgsReferencedRectangle, QgsSingleBandGrayRenderer, QgsVectorLayer)
    from qgis.PyQt.QtCore import QSettings
    from qgis.PyQt.QtGui import QFontDatabase
    import qgis._core
    output = Path(config['output'])
    QgsApplication.setPrefixPath(config['qgis_prefix'], True)
    app = QgsApplication([], True); app.initQgis()
    try:
        require(Path(qgis._core.__file__).resolve().is_relative_to(Path(config['qgis_prefix']).resolve()), 'host PyQGIS imported')
        font_id = QFontDatabase.addApplicationFont(config['font_file'])
        require(font_id >= 0, 'retained font failed to load')
        font_families = QFontDatabase.applicationFontFamilies(font_id)
        require(bool(font_families), 'retained font has no family')
        assets = make_data(output, config['gdal_library'])
        project = QgsProject.instance(); project.setCrs(QgsCoordinateReferenceSystem('EPSG:4326'))
        project.setTitle('F02-04 synthetic spatial witness')
        local = QgsVectorLayer(str(output/'points.geojson'), 'local_points', 'ogr')
        uri = QgsDataSourceUri(); uri.setConnection('qgis_fixture', 'fixture_qgis', '', '')
        uri.setDataSource('public', 'points', 'geom', '', 'id')
        database = QgsVectorLayer(uri.uri(False), 'database_points', 'postgres')
        raster = QgsRasterLayer(str(output/'known.tif'), 'known_raster', 'gdal')
        for layer in (raster, local, database):
            require(layer.isValid(), 'fixture provider failed: ' + layer.name())
            layer.serverProperties().setShortName(layer.name()); project.addMapLayer(layer)
        for layer, color, size, shape in ((local,'220,20,30,255','5','circle'),(database,'20,60,230,255','2','square')):
            layer.renderer().setSymbol(QgsMarkerSymbol.createSimple({'name':shape,'color':color,'outline_style':'no','size':size}))
        renderer = QgsSingleBandGrayRenderer(raster.dataProvider(),1)
        contrast = QgsContrastEnhancement(raster.dataProvider().dataType(1))
        contrast.setContrastEnhancementAlgorithm(QgsContrastEnhancement.StretchToMinimumMaximum)
        contrast.setMinimumValue(0); contrast.setMaximumValue(255); renderer.setContrastEnhancement(contrast)
        raster.setRenderer(renderer)
        project.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(QgsRectangle(0,0,4,4), project.crs()))
        project.writeEntry('WMSServiceCapabilities','/',True)
        project.writeEntry('WMSServiceTitle','/','F02-04 synthetic spatial witness')
        project.writeEntry('WMSCrsList','/', ['EPSG:4326','EPSG:3857'])
        project.setFileName(str(output/'fixture.qgs'))
        require(project.write(), 'project write failed')
        layers = check_layers(project)
        transform = QgsCoordinateTransform(QgsCoordinateReferenceSystem('EPSG:4326'), QgsCoordinateReferenceSystem('EPSG:3857'), project)
        transform.setAllowFallbackTransforms(False); transform.setBallparkTransformsAreAppropriate(False)
        projected = transform.transform(QgsPointXY(1,1))
        expected = [111319.49079327357,111325.1428663851]
        require(abs(projected.x()-expected[0])<1e-6 and abs(projected.y()-expected[1])<1e-6, 'CRS numerical witness failed')
        a = QgsGeometry.fromWkt('POLYGON((0 0,2 0,2 2,0 2,0 0))')
        b = QgsGeometry.fromWkt('POLYGON((1 1,3 1,3 3,1 3,1 1))')
        intersection = a.intersection(b)
        require(abs(intersection.area()-1.0)<1e-12 and intersection.isGeosEqual(QgsGeometry.fromWkt('POLYGON((1 1,2 1,2 2,1 2,1 1))')), 'GEOS intersection failed')
        profile = output/'profiles/profiles/f02-04/QGIS/QGIS3.ini'; profile.parent.mkdir(parents=True)
        settings = QSettings(str(profile), QSettings.IniFormat)
        # Exact app/main.cpp reads these before constructing desktop widgets.
        settings.setValue('app/fontFamily',font_families[0])
        settings.setValue('app/fontPointSize',12)
        settings.setValue('core/httpsfeedqgisorg/disabled',True)
        settings.setValue('qgis/checkVersion',False); settings.setValue('plugins/checkOnStart',False); settings.sync()
        report = {'result_exit_code':0,'assets':assets,'layers':layers,'qgis_version':Qgis.QGIS_VERSION,
            'project_sha256':sha(output/'fixture.qgs'),'bindings':str(qgis._core.__file__),
            'loaded_origins':loaded_origins(config),'provider_origins':provider_origins(config),'python_origins':python_origins(config),'font':{'path':config['font_file'],'sha256':sha(config['font_file']),
                'families':font_families},
            'crs':{'source':'EPSG:4326','target':'EPSG:3857','input':[1,1],'expected':expected,
                'actual':[projected.x(),projected.y()],'tolerance_m':1e-6,'ballpark_allowed':False,'fallback_allowed':False,
                'resource_sha256':sha(Path(os.environ['PROJ_DATA'])/'proj.db')},
            'geos':{'operation':'intersection','expected_area':1.0,'actual_area':intersection.area(),'equals_expected_geometry':True}}
        save(output/'fixture-result.json',report)
        project.clear()
    finally: app.exitQgis()


if __name__ == '__main__': generate(json.loads(Path(sys.argv[1]).read_text()))
