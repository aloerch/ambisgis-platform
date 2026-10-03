import json
from pathlib import Path
import tempfile
import unittest

from successor_build import COMMIT, TREE
from successor_stage import verify_build, verify_composition


class SuccessorStageGuards(unittest.TestCase):
    def test_reject_old_successful_build(self):
        with tempfile.TemporaryDirectory() as root:
            attempt = Path(root)
            for update in ({'commit':'1a4cda5f2620e7374e5926fc955a7d2d06493e15'},
                           {'tree':'0'*40}, {'state':'started'}, {'result_exit_code':1}):
                value = dict(commit=COMMIT, tree=TREE, state='compiled-staged', result_exit_code=0)
                value.update(update)
                (attempt/'result.json').write_text(json.dumps(value))
                with self.assertRaisesRegex(ValueError, 'exact successor'):
                    verify_build(attempt)

    def test_nonresource_tamper_or_omission_fails(self):
        binary = {'path':'bin/qgis','sha256':'new-build'}
        palette = {'path':'share/qgis/resources/cpt-city-qgis-min/cb/ramp.svg','sha256':'source'}
        verify_composition([binary], [binary,palette], [palette])
        for changed in ([palette], [dict(binary,sha256='old-build'),palette],
                        [binary,{'path':'lib/foreign.so'},palette]):
            with self.assertRaisesRegex(ValueError, 'non-resource'):
                verify_composition([binary], changed, [palette])

    def test_resource_tamper_or_reintroduction_fails(self):
        binary = {'path':'bin/qgis','sha256':'new-build'}
        for row in ({'path':'share/qgis/resources/cpt-city-qgis-min/omitted.svg'},
                    {'path':'share/qgis/doc/ambisgis-resource-selection/foreign.txt'}):
            with self.assertRaisesRegex(ValueError, 'exact source projection'):
                verify_composition([binary], [binary,row], [])


if __name__ == '__main__':
    unittest.main()
