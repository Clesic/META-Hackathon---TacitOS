"""Validate synthetic fixtures and links; does not test an AI or application."""
from pathlib import Path
import collections
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.grade import grade as oracle

def validate():
    cases = json.loads((ROOT/'03-scenarios/cases.json').read_text())['cases']
    expected = json.loads((ROOT/'03-scenarios/evaluator-only/expected.json').read_text())['expected']
    rules = json.loads((ROOT/'03-scenarios/expert-only/rulebook.json').read_text())['rules']
    ids = [c['case_id'] for c in cases]
    errors = []
    if len(set(ids)) != len(ids): errors.append('Duplicate case IDs')
    if set(ids) != set(expected): errors.append('Case/oracle IDs differ')
    if len(cases) != 22: errors.append('Expected 22 prepared cases')
    if len({r['rule_id'] for r in rules}) != 3: errors.append('Expected three unique rules')
    for c in cases:
        cid = c['case_id']
        if c['data_class'] != 'synthetic': errors.append(f'{cid}: unlabelled data')
        if c['split'] not in ('discovery','transfer','boundary','control'): errors.append(f'{cid}: invalid split')
        if any(k in c for k in ('expected_action','expert_answer','accept_if')): errors.append(f'{cid}: visible oracle leakage')
        exp = expected.get(cid, {})
        result = oracle(c)
        if result != exp.get('expected_action'): errors.append(f'{cid}: oracle mismatch')
        if result not in c['allowed_actions']: errors.append(f'{cid}: forbidden expected action')
        if exp.get('independently_completable') != (result in ('accept','reject')): errors.append(f'{cid}: completion mismatch')
    for family in ('substitution','duplicate','delivery'):
        splits = collections.Counter(c['split'] for c in cases if c['family'] == family)
        if splits != {'discovery':1,'transfer':2,'boundary':3}: errors.append(f'{family}: wrong split coverage')
    links = 0
    for p in ROOT.rglob('*.md'):
        if any(part in {'.venv', '.git', 'node_modules'} for part in p.relative_to(ROOT).parts):
            continue
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', p.read_text()):
            if '://' in target or target.startswith('#'): continue
            target = target.split('#')[0]
            links += 1
            if not (p.parent/target).exists(): errors.append(f'{p.relative_to(ROOT)}: broken link {target}')
    results = json.loads((ROOT/'04-evaluation/results-template.json').read_text())
    if results['status'] != 'not_run' or results['attempts']: errors.append('Template must not invent results')
    if errors:
        raise SystemExit('\n'.join(errors))
    print(f'PASS: {len(cases)} synthetic cases, 3 rule families, oracle consistency and {links} local links.')
    print('This validates preparation assets only. No model or product evaluation has run.')

if __name__ == '__main__':
    validate()
