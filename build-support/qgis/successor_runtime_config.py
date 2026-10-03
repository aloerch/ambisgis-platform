#!/usr/bin/env python3
"""Bind unchanged native/runtime witnesses to the newly compiled/staged bytes."""
import argparse
import json
from pathlib import Path
import shutil
from xml.sax.saxutils import escape

from common import require, sha, save, verify_inventory
from successor_build import COMMIT, TREE, publication
from successor_stage import verify_build

GDAL_MANIFEST = 'a3d08a8ff3d8a811f54c117589475ca0f267c47372b7d5d6599fea2c78c389f6'
GDAL_SUCCESS = '56953263d539cc42a0e860f3b7920aef14f5f4985284312065628a3b1561daf5'


def create(attempt, stage, selection, output):
    require(not output.exists(), 'fresh runtime configuration required')
    verify_build(attempt)
    report = json.loads((stage/'result.json').read_text())
    manifest = stage/'manifest.json'
    require(report['result_exit_code'] == 0 and report['source_commit'] == COMMIT and report['source_tree'] == TREE
            and report['manifest_sha256'] == sha(manifest)
            and report['build_manifest_sha256'] == sha(attempt/'compile/output-manifest.json'),
            'runtime stage must bind exact successful successor build')
    prefix = stage/'prefix'
    staged = json.loads(manifest.read_text())
    require(staged['prefix'] == str(prefix), 'runtime stage prefix redirected')
    verify_inventory(prefix,staged['files'])
    require(sha(selection) == publication.SELECTION_SHA, 'wrong resource selection')
    receipt = json.loads((attempt/'compile/receipt.json').read_text())
    native = Path(receipt['native_prefix']); spatial = Path(receipt['spatial_prefix'])
    support = Path(receipt['support_prefix']); xml = Path(receipt['xml_profile']['prefix'])
    bindings = support.parent/'python-gdal-02'
    require(sha(bindings/'output-manifest.json') == GDAL_MANIFEST and
            sha(bindings/'success.json') == GDAL_SUCCESS, 'retained GDAL bindings evidence changed')
    verify_inventory(bindings/'python',json.loads((bindings/'output-manifest.json').read_text())['files'])
    source = attempt/'compile/sources/qgis-successor'
    font_relative = 'tests/testdata/font/QGIS-Vera/QGIS-Vera.ttf'
    source_rows = json.loads((attempt/'compile/source-manifest.json').read_text())
    expected_font = next(row for row in source_rows if row['path'] == font_relative)
    require(sha(source/font_relative) == expected_font['sha256'], 'source fixture font changed')
    fonts = output.with_suffix('') / 'fonts'
    fonts.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(source/font_relative,fonts/'QGIS-Vera.ttf')
    fontconfig = fonts.parent/'fonts.conf'
    fontconfig.write_text('<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd"><fontconfig><dir>'+
                          escape(str(fonts))+'</dir></fontconfig>\n')
    config = {'qgis_prefix':str(prefix),'qgis_build':str(attempt/'compile/build'),'qgis_source':str(source),
        'desktop':str(prefix/'bin/qgis'),'server':str(prefix/'bin/qgis_mapserver'),
        'provider_path':str(prefix/'lib/qgis/plugins'),'python':'/usr/bin/python3.13',
        'database_prefix':str(native),'database_evidence':str(native.parent.parent/'run-003-evidence-final.json'),
        'spatial_prefix':str(spatial),'support_prefix':str(support),'xml_prefix':str(xml),
        'qt_plugins':str(support/'usr/lib64/qt5/plugins'),
        'font_file':str(source/font_relative),'fontconfig_file':str(fontconfig),
        'gdal_library':str(spatial/'lib/libgdal.so'),'gdal_data':str(spatial/'share/gdal'),
        'proj_data':str(spatial/'share/proj'),
        'library_paths':[str(root/path) for root,path in ((xml,'lib'),(prefix,'lib'),(spatial,'lib'),
            (native,'lib'),(support,'usr/lib64'),(support,'usr/lib'))],
        'python_paths':[str(prefix/'share/qgis/python'),str(support/'usr/lib64/python3.13/site-packages'),
            str(support/'usr/lib/python3.13/site-packages'),str(bindings/'python')],
        'resource_manifest':str(manifest),'resource_manifest_sha256':sha(manifest),
        'resource_selection':str(selection),'resource_selection_sha256':sha(selection),
        'successor':{'commit':COMMIT,'tree':TREE,'build_result_sha256':sha(attempt/'result.json'),
                     'stage_result_sha256':sha(stage/'result.json'),'gdal_bindings_manifest_sha256':GDAL_MANIFEST}}
    require(Path(config['database_evidence']).is_file(), 'owned database evidence absent')
    save(output,config)
    return config


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('build-attempt','stage','selection','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    create(args.build_attempt.resolve(),args.stage.resolve(),args.selection.resolve(),args.output.resolve())
