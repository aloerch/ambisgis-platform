#!/usr/bin/env python3
"""Render planned GitHub issue bodies/fields from local files; never call GitHub.

Print JSON by default. --out writes one new local file, refusing existing paths.
Remote IDs, current progress, and user edits are deliberately outside this seed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def component(task: dict[str, Any]) -> str:
    prefix = task['id'].split('-')[0]
    if prefix == 'DB': return 'Database'
    if prefix == 'QGIS': return 'Desktop'
    if prefix == 'NB': return 'Notebooks'
    if prefix == 'SRV': return 'Server'
    if prefix in {'WEB', 'UX'}: return 'Web apps'
    if prefix in {'GOV', 'OWN'}: return 'Governance'
    if prefix in {'SEC', 'REL', 'OPS', 'QA'}: return 'Security/Release'
    return 'Platform'


def review_gate(task: dict[str, Any]) -> str:
    prefix = task['id'].split('-')[0]
    if prefix == 'SEC': return 'Security'
    if prefix == 'DB': return 'Data migration'
    if task['id'] in {'FND-02', 'REL-01'}: return 'License/Brand'
    if prefix == 'REL': return 'Release'
    return 'Human approval' if task['human_review_required'] else 'Standard PR'


def build_seed(root: Path = ROOT) -> dict[str, Any]:
    manifest = json.loads((root / 'repositories.json').read_text(encoding='utf-8'))
    project = json.loads((root / 'project.json').read_text(encoding='utf-8'))
    tasks = json.loads((root / 'backlog.json').read_text(encoding='utf-8'))['tasks']
    allowed = {r['name'] for r in manifest['repositories']}
    if project['owner'] != manifest['owner'] or set(project['repositories']) != allowed:
        raise ValueError('Project owner/repositories do not match the approved manifest.')
    ids = {t['id'] for t in tasks}
    if len(ids) != len(tasks): raise ValueError('Duplicate Task ID.')
    issues: list[dict[str, Any]] = []
    for task in sorted(tasks, key=lambda t: (t['phase'], t['id'])):
        if task['repository'] not in allowed or not set(task['dependencies']) <= ids:
            raise ValueError(f"Invalid repository/dependency for {task['id']}")
        marker = f"<!-- ambisgis:task:{task['id']} -->"
        dep = ', '.join(task['dependencies']) or 'None'
        lines = [marker, '<!-- ambisgis:managed:start -->',
                 f"## {task['id']} — {task['title']}", '',
                 f"Phase: {task['phase']} · Repository: {task['repository']}",
                 f"Requirements: {', '.join(task['requirement_ids'])}",
                 f"Depends on: {dep}", '', '### Deliverables']
        lines += [f'- {d}' for d in task['deliverables']]
        lines += ['', '### Acceptance criteria']
        lines += [f'- [ ] {a}' for a in task['acceptance']]
        lines += ['', '### Planned verification', ', '.join(task['tests']), '',
                  f"Risk: {task['risk']} · Review gate: {review_gate(task)}", '',
                  'Specification: version-controlled plan/backlog.json and relevant plan/docs chapters.',
                  'These are planned tests, not test results. Attach actual commit/PR/test evidence.',
                  '<!-- ambisgis:managed:end -->', '',
                  '### Implementation discussion and evidence',
                  'Preserve manually added content below this section during plan updates.', '']
        body = '\n'.join(lines)
        fields = {'Task ID': task['id'], 'Delivery': 'Backlog', 'Phase': task['phase'],
                  'Component': component(task),
                  'Priority': 'Critical' if task['risk'] == 'critical' else ('High' if task['risk'] == 'high' else 'Normal'),
                  'Risk': task['risk'].capitalize(), 'Review gate': review_gate(task)}
        issues.append({'task_id': task['id'], 'repository': f"{manifest['owner']}/{task['repository']}",
                       'title': f"[{task['id']}] {task['title']}", 'marker': marker,
                       'body': body, 'spec_sha256': hashlib.sha256(json.dumps(task, sort_keys=True).encode()).hexdigest(),
                       'dependency_task_ids': task['dependencies'],
                       'labels': ['ambisgis-managed', f"phase:{task['phase'].lower()}", f"risk:{task['risk']}"],
                       'initial_fields_only': fields})
    return {'schema_version': 1, 'kind': 'local seed; NOT a remote receipt or completed provisioning',
            'owner': project['owner'], 'project_title': project['title'], 'project_marker': project['marker'],
            'visibility': project['visibility'], 'issue_count': len(issues), 'issues': issues}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, help='Write a NEW local JSON file; existing paths are refused.')
    args = parser.parse_args(argv)
    try:
        text = json.dumps(build_seed(), indent=2, ensure_ascii=False) + '\n'
        if args.out is None:
            print(text, end='')
        else:
            with args.out.open('x', encoding='utf-8') as stream:
                stream.write(text)
            print(f'Wrote local seed: {args.out}. No GitHub requests were made.')
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(f'Seed export failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
