#!/usr/bin/env python3
"""Validate plan structure and, when installed, full JSON schema examples.

No network access and no GitHub actions. --require-schemas fails rather than
skipping when the optional jsonschema validation package is unavailable.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


def validate_plan(root: Path = ROOT) -> dict[str, int]:
    for path in root.rglob('*.json'):
        if '__pycache__' not in path.parts and not path.name.startswith('.'):
            json.loads(path.read_text(encoding='utf-8'))
    manifest = json.loads((root/'repositories.json').read_text())
    repos = {r['name'] for r in manifest['repositories']}
    if len(repos) != 15:
        raise ValueError('Expected fifteen unique repositories.')
    tasks = json.loads((root/'backlog.json').read_text())['tasks']
    requirements = json.loads((root/'requirements.json').read_text())['requirements']
    by_id = {t['id']:t for t in tasks}
    by_req = {r['id']:r for r in requirements}
    if len(by_id) != len(tasks) or len(by_req) != len(requirements):
        raise ValueError('Duplicate task or requirement IDs.')
    covered: set[str] = set()
    tests: set[str] = set()
    for task in tasks:
        if task['repository'] not in repos:
            raise ValueError(f"Unknown repository in {task['id']}")
        if not task['deliverables'] or not task['acceptance'] or not task['tests']:
            raise ValueError(f"Missing task acceptance/deliverable/test: {task['id']}")
        for dep in task['dependencies']:
            if dep not in by_id or dep == task['id']:
                raise ValueError(f"Invalid dependency {task['id']} -> {dep}")
        if not set(task['requirement_ids']) <= by_req.keys():
            raise ValueError(f"Unknown requirement in {task['id']}")
        covered.update(task['requirement_ids']); tests.update(task['tests'])
    if covered != by_req.keys():
        raise ValueError('Some requirements have no implementation task.')
    for req in requirements:
        if not set(req['tests']) <= tests:
            raise ValueError(f"Unmapped test for {req['id']}")
    visiting: set[str] = set(); visited: set[str] = set()
    def visit(task_id: str):
        if task_id in visiting:
            raise ValueError(f'Dependency cycle at {task_id}')
        if task_id in visited:
            return
        visiting.add(task_id)
        for dependency in by_id[task_id]['dependencies']:
            visit(dependency)
        visiting.remove(task_id); visited.add(task_id)
    for task in tasks:
        visit(task['id'])
    source_text = (root/'SOURCES.md').read_text()
    source_ids = set(re.findall(r'\| (S\d{2}) \|', source_text))
    for path in (root/'docs').glob('*.md'):
        used = set(re.findall(r'\bS\d{2}\b', path.read_text()))
        if used - source_ids:
            raise ValueError(f'Unknown source IDs in {path.name}: {used-source_ids}')
    for needed in ['README.md','AGENTS.md','CODEX_START_PROMPT.md','DECISIONS.md','STATUS.md']:
        if not (root/needed).is_file():
            raise ValueError(f'Missing {needed}')
    return {'repositories':len(repos),'tasks':len(tasks),'requirements':len(requirements),'sources':len(source_ids)}


def validate_examples(root: Path = ROOT) -> int:
    from jsonschema import Draft202012Validator, FormatChecker
    pairs = [('publication','publication'),('edit-request','edit-request'),
             ('post-request','post-request'),('application','application')]
    for schema_name, example_name in pairs:
        schema=json.loads((root/'contracts'/f'{schema_name}.schema.json').read_text())
        example=json.loads((root/'examples'/f'{example_name}.json').read_text())
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema,format_checker=FormatChecker()).validate(example)
    # Referential integrity is beyond structural JSON Schema and checked explicitly.
    app=json.loads((root/'examples'/'application.json').read_text())
    sources={s['id'] for s in app['data_sources']}; widgets={w['id'] for w in app['widgets']}
    if len(sources)!=len(app['data_sources']) or len(widgets)!=len(app['widgets']):
        raise ValueError('Duplicate application source/widget identity.')
    for widget in app['widgets']:
        if widget.get('data_source_id') is not None and widget['data_source_id'] not in sources:
            raise ValueError('Unknown application data source.')
    for page in app['pages']:
        for layout in page['layouts'].values():
            if any(p['widget_id'] not in widgets for p in layout):
                raise ValueError('Unknown layout widget.')
    return len(pairs)


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-schemas',action='store_true')
    args=parser.parse_args(argv)
    try:
        results=validate_plan()
        print('Plan references and acyclic dependencies: PASS',results)
        try:
            number=validate_examples()
            print(f'JSON Schema 2020-12 and format/example checks: PASS ({number} schemas/examples)')
        except ModuleNotFoundError:
            if args.require_schemas:
                raise ValueError('Install requirements-validation.txt in an isolated environment to validate schemas.')
            print('SKIPPED full schema checks: optional jsonschema package missing. Use --require-schemas to make this blocking.')
        return 0
    except Exception as exc:
        print(f'VALIDATION FAILED: {exc}',file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
