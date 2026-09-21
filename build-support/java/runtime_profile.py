"""Explicit WAR-bound headless Marlin/NO-ORACLE runtime selection."""
import json
from pathlib import Path
import re
from resolution import sha

MEMBER = 'WEB-INF/lib/marlin-0.9.4.8.jar'


def load(path, inventory, output):
    if path is None:
        return None
    path = Path(path)
    profile = json.loads(path.read_text())
    if (profile.get('schema_version') != 1 or profile.get('profile') != 'NO-ORACLE-headless-Temurin17'
            or profile.get('war_sha256') != inventory['war_sha256']
            or profile.get('renderer_member') != MEMBER
            or not re.fullmatch('[0-9a-f]{64}', profile.get('renderer_sha256', ''))):
        raise ValueError('explicit Java runtime profile differs from selected WAR')
    renderer = Path(output).resolve() / 'lib' / Path(MEMBER).name
    if renderer.is_symlink() or sha(renderer) != profile['renderer_sha256']:
        raise ValueError('packaged renderer differs from runtime profile')
    return {**profile, 'renderer_path': str(renderer), 'profile_source': str(path.resolve()),
            'profile_manifest_sha256': sha(path)}


def flags(profile, war):
    if profile is None:
        return []
    if profile.get('profile') != 'NO-ORACLE-headless-Temurin17' or sha(war) != profile['war_sha256']:
        raise ValueError('runtime WAR changed')
    path = Path(profile['renderer_path'])
    if path.is_symlink() or sha(path) != profile['renderer_sha256']:
        raise ValueError('runtime renderer changed')
    if sha(profile['profile_source']) != profile['profile_manifest_sha256']:
        raise ValueError('runtime profile changed')
    return ['--patch-module', 'java.desktop=' + str(path),
            '--add-exports', 'java.desktop/sun.java2d.pipe=ALL-UNNAMED',
            '-Dsun.java2d.opengl=false', '-Dsun.java2d.renderer=sun.java2d.marlin.DMarlinRenderingEngine',
            '-Dambisgis.fixture.renderer=' + str(path), '-Dambisgis.fixture.noOracle=true']
