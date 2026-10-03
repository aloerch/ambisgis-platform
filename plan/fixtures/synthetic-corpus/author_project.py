#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Recreate the checked-in QGIS template using an explicitly selected runtime.

Run only in the retained owned PyQGIS environment against a disposable generated
small corpus. Removes author/time metadata and replaces random layer IDs with
fixed fixture IDs before writing the template. Does not alter source datasets.
"""
import argparse
import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET
from qgis.core import (Qgis, QgsApplication, QgsCategorizedSymbolRenderer,
    QgsCoordinateReferenceSystem, QgsFillSymbol, QgsLineSymbol, QgsMarkerSymbol,
    QgsPalLayerSettings, QgsProject, QgsRectangle, QgsReferencedRectangle,
    QgsRendererCategory, QgsTextFormat, QgsVectorLayer, QgsVectorLayerSimpleLabeling,
    QgsRasterLayer)
from qgis.PyQt.QtGui import QFont, QColor, QFontDatabase


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('corpus', type=Path)
    parser.add_argument('template', type=Path)
    parser.add_argument('--font-file', type=Path, required=True)
    args = parser.parse_args()
    assert hashlib.sha256(args.font_file.read_bytes()).hexdigest() == '08a82cf71e13669f725bccdfeff7ed8dc0e43ffdeac22633074399098112d3e3'
    app = QgsApplication([], False); app.initQgis()
    assert Qgis.QGIS_DEV_VERSION == '86af40542b219b0da6df1a43914413443330c0c0'
    font_id = QFontDatabase.addApplicationFont(str(args.font_file)); assert font_id >= 0
    family = QFontDatabase.applicationFontFamilies(font_id)[0]
    project = QgsProject()
    project.setCrs(QgsCoordinateReferenceSystem('EPSG:4326'))
    project.setTitle('Synthetic corpus: categories, labels, holes, roads and multiband raster')
    ids = {}
    for name in ('addresses', 'roads', 'parcels'):
        layer = QgsVectorLayer(str(args.corpus / (name + '.geojson')), name, 'ogr')
        assert layer.isValid()
        if name == 'addresses':
            categories = []
            for value, color in [('north', '#c43c39'), ('south', '#3264c8'),
                                 ('east', '#347d3b'), ('west', '#a36c00')]:
                symbol = QgsMarkerSymbol.createSimple({'name': 'circle', 'color': color,
                                                       'size': '3', 'outline_style': 'no'})
                categories.append(QgsRendererCategory(value, symbol, value))
            layer.setRenderer(QgsCategorizedSymbolRenderer('district', categories))
            labels = QgsPalLayerSettings()
            labels.fieldName = 'coalesce("name", \'unnamed\')'; labels.isExpression = True
            fmt = QgsTextFormat(); fmt.setFont(QFont(family)); fmt.setSize(10)
            fmt.setColor(QColor('#303030')); labels.setFormat(fmt)
            layer.setLabeling(QgsVectorLayerSimpleLabeling(labels)); layer.setLabelsEnabled(True)
        elif name == 'roads':
            layer.renderer().setSymbol(QgsLineSymbol.createSimple(
                {'line_color': '#9b6500', 'line_width': '0.8', 'line_style': 'dash'}))
        else:
            layer.renderer().setSymbol(QgsFillSymbol.createSimple(
                {'color': '#adc5a3', 'outline_color': '#203040', 'outline_width': '0.4'}))
        ids[layer.id()] = name + '_fixture'
        project.addMapLayer(layer)
    raster = QgsRasterLayer(str(args.corpus / 'raster/multiband.vrt'), 'multiband', 'gdal')
    assert raster.isValid(); ids[raster.id()] = 'multiband_fixture'; project.addMapLayer(raster)
    project.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(
        QgsRectangle(-117.003, 31.998, -116.975, 32.012), project.crs()))
    path = args.corpus / 'authoring.qgs'
    project.setFileName(str(path)); assert project.write()
    text = path.read_text()
    for old, new in ids.items():
        text = text.replace(old, new)
    root = ET.fromstring(text)
    for key in ('saveUser', 'saveUserFull', 'saveDateTime'):
        root.attrib.pop(key, None)
    for parent in root.iter():
        for child in list(parent):
            if child.tag == 'creation' or (child.tag == 'date' and parent.tag == 'dates'):
                parent.remove(child)
    assert all(not str(args.corpus) in (node.text or '') for node in root.iter())
    ET.indent(root)
    ET.ElementTree(root).write(args.template, encoding='utf-8', xml_declaration=True)
    project.clear()
    del project, layer, raster
    app.exitQgis()


if __name__ == '__main__':
    main()
