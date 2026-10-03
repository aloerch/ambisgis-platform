"""Spatial/color and desktop comparison assertions over actual HTTP PNG bytes."""
import hashlib
import json
from pathlib import Path
import sys
from PIL import Image, ImageChops, ImageStat, __version__ as pillow_version


def check(image, layer):
    assert image.size == (512, 512)
    rgb = image.convert('RGB')
    probes = []
    expected = {'public_points': [(1,1,(220,20,30)), (3,1,(20,60,230)), (2,3,(220,20,30))],
                'private_points': [(1,1,(0,128,64)), (3,1,(0,128,64)), (2,3,(0,128,64))],
                'rich_points': [(1,1,(0,128,64)), (3,1,(0,128,64)), (2,3,(0,128,64))],
                'group_points': [(1,2,(224,128,0)), (2,2,(224,128,0)), (3,2,(224,128,0))],
                'parcels': [(1,1,(128,96,192))],
                'elevation':[(.5,3.5,(40,40,40)),(3.5,3.5,(90,90,90)),(.5,.5,(150,150,150)),(3.5,.5,(210,210,210))]}
    for x,y,color in expected[layer]:
        px,py = round(x*128), round((4-y)*128)
        pixels = [rgb.getpixel((ix,iy)) for ix in range(px-12,px+13) for iy in range(py-12,py+13)]
        matches = sum(all(abs(a-b) <= 20 for a,b in zip(pixel,color)) for pixel in pixels)
        assert matches >= (50 if layer != 'group_points' else 40), (layer,x,y,matches)
        probes.append({'xy':[x,y],'rgb':color,'matching_pixels':matches})
    if layer == 'rich_points':
        for x,y,_ in expected[layer]:
            px,py = round(x*128), round((4-y)*128)
            dark = sum(max(rgb.getpixel((ix,iy))) < 100 for ix in range(px, min(px+120,512))
                       for iy in range(max(0,py-40),py))
            assert dark > 60, ('rich label missing',x,y,dark)
            probes.append({'xy':[x,y],'dark_label_pixels':dark})
    return probes


def main(path):
    spec = json.loads(Path(path).read_text()); results = []; seen = {}
    for row in spec['images']:
        data = Path(row['path']).read_bytes(); digest = hashlib.sha256(data).hexdigest()
        key = row['layer'] + ':' + digest
        if key not in seen:
            with Image.open(row['path']) as image:
                probes = check(image, row['layer'])
                with Image.open(Path(spec['desktop']) / (row['layer'] + '.png')) as desktop:
                    difference = ImageChops.difference(image.convert('RGB'), desktop.convert('RGB'))
                    mean = sum(ImageStat.Stat(difference).mean)/3
                    # Independent semantic probes above prevent blank/misplaced data from
                    # exploiting a mostly-white image's low average pixel difference.
                    assert mean <= 3.0, (row['layer'], row['route'], mean)
                    seen[key] = {'probes':probes,'mean_absolute_error':mean,'limit':3.0}
        results.append(dict(row,sha256=digest,checks=seen[key],passed=True))
    # Prove the output assertion fails on a blank image rather than checking only PNG validity.
    try: check(Image.new('RGB',(512,512),'white'),'public_points')
    except AssertionError: pass
    else: raise AssertionError('blank image negative control passed')
    report={'status':'passed','pillow_version':pillow_version,'images':results,'unique_decoded_maps':len(seen),
            'blank_image_rejected':True}
    Path(spec['output']).write_text(json.dumps(report,indent=2)+'\n')


if __name__ == '__main__': main(sys.argv[1])
