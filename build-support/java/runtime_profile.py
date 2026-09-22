"""Explicit WAR-bound headless selections, including optional JPEG2000 exclusion."""
import json
from pathlib import Path
import re
from resolution import sha

MEMBER = 'WEB-INF/lib/marlin-0.9.4.8.jar'
NO_JPEG2000 = 'NO-ORACLE-NO-JPEG2000-headless-Temurin17'
PROFILES = ('NO-ORACLE-headless-Temurin17', NO_JPEG2000)
REPLACED_MEMBERS = {'json': 'WEB-INF/lib/json-lib-2.4.2-geoserver.jar',
                    'imageio': 'WEB-INF/lib/jai_imageio-1.1.jar'}


def load(path, inventory, output):
    if path is None:
        return None
    path = Path(path)
    profile = json.loads(path.read_text())
    if (profile.get('schema_version') != 1 or profile.get('profile') not in PROFILES
            or profile.get('war_sha256') != inventory['war_sha256']
            or profile.get('renderer_member') != MEMBER
            or not re.fullmatch('[0-9a-f]{64}', profile.get('renderer_sha256', ''))):
        raise ValueError('explicit Java runtime profile differs from selected WAR')
    renderer = Path(output).resolve() / 'lib' / Path(MEMBER).name
    if renderer.is_symlink() or sha(renderer) != profile['renderer_sha256']:
        raise ValueError('packaged renderer differs from runtime profile')
    if profile['profile'] == NO_JPEG2000:
        for key, member in REPLACED_MEMBERS.items():
            selected = Path(output).resolve() / 'lib' / Path(member).name
            if (profile.get(key + '_member') != member or selected.is_symlink()
                    or not re.fullmatch('[0-9a-f]{64}', profile.get(key + '_sha256', ''))
                    or sha(selected) != profile[key + '_sha256']):
                raise ValueError('packaged ' + key + ' differs from NO-JPEG2000 profile')
            profile[key + '_path'] = str(selected)
    return {**profile, 'renderer_path': str(renderer), 'profile_source': str(path.resolve()),
            'profile_manifest_sha256': sha(path)}


def flags(profile, war):
    if profile is None:
        return []
    if profile.get('profile') not in PROFILES or sha(war) != profile['war_sha256']:
        raise ValueError('runtime WAR changed')
    path = Path(profile['renderer_path'])
    if path.is_symlink() or sha(path) != profile['renderer_sha256']:
        raise ValueError('runtime renderer changed')
    if sha(profile['profile_source']) != profile['profile_manifest_sha256']:
        raise ValueError('runtime profile changed')
    additional = []
    if profile['profile'] == NO_JPEG2000:
        for key in REPLACED_MEMBERS:
            selected = Path(profile[key + '_path'])
            if selected.is_symlink() or sha(selected) != profile[key + '_sha256']:
                raise ValueError('runtime ' + key + ' changed')
        additional.append('-Dambisgis.fixture.noJpeg2000=true')
    return additional + ['--patch-module', 'java.desktop=' + str(path),
            '--add-exports', 'java.desktop/sun.java2d.pipe=ALL-UNNAMED',
            '-Dsun.java2d.opengl=false', '-Dsun.java2d.renderer=sun.java2d.marlin.DMarlinRenderingEngine',
            '-Dambisgis.fixture.renderer=' + str(path), '-Dambisgis.fixture.noOracle=true']
