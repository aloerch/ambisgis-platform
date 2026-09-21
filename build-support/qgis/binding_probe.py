"""Real matching GDAL binding raster round trip and loaded native origin witness."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('spatial','native','bindings'): parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    from osgeo import gdal, _gdal, ogr, osr, gdal_array
    import numpy as np
    gdal.UseExceptions()
    values=np.array([[2,5],[11,19]],dtype=np.int16)
    dataset=gdal.GetDriverByName('MEM').Create('',2,2,1,gdal.GDT_Int16)
    assert dataset.GetRasterBand(1).WriteArray(values)==0
    assert np.array_equal(dataset.ReadAsArray(),values)
    paths=sorted({line.split()[-1] for line in Path('/proc/self/maps').read_text().splitlines()
                  if '/' in line and any(stem in line for stem in ('libgdal.','libproj.','libgeos','libsqlite'))})
    assert Path(_gdal.__file__).resolve().is_relative_to(args.bindings.resolve())
    for stem in ('libgdal.','libproj.','libsqlite'):
        actual=[Path(p).resolve() for p in paths if stem in Path(p).name]
        assert len(actual)==1 and actual[0].is_relative_to(args.spatial.resolve()),(stem,actual)
    actual=[Path(p).resolve() for p in paths if 'libgeos' in Path(p).name]
    assert len(actual)==2 and all(p.is_relative_to(args.native.resolve()) for p in actual)
    def entry(path):
        p=Path(path)
        with p.open('rb') as stream: digest=hashlib.file_digest(stream,'sha256').hexdigest()
        return {'path':str(p),'sha256':digest}
    print(json.dumps({'gdal_extension':entry(_gdal.__file__),
          'spatial_mappings':[entry(p) for p in paths],'numpy_mem_roundtrip':True},sort_keys=True))

if __name__=='__main__':main()
