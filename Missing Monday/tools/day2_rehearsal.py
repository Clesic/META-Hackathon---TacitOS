"""Run one capture-to-transfer rehearsal. The expert answer is supplied only after diagnosis."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.server import Store

FORBIDDEN = ('may replace', 'only on machine revisions', 'original is cancelled', 'explicitly a replacement', 'accept_if')

def main():
    database = ROOT / 'runs' / 'day2-rehearsal.sqlite3'
    if database.exists():
        database.unlink()
    store = Store(database)
    sid = store.create()
    discovery = store.start(sid, 'S01')
    store.inspect(sid, discovery, 'case-facts')
    store.inspect(sid, discovery, 'handbook-v1')
    diagnosis = store.diagnose(sid, discovery)
    diagnosis_text = f"{diagnosis['missing_distinction']} {diagnosis['expert_question']}".lower()
    leaks = [phrase for phrase in FORBIDDEN if phrase in diagnosis_text]
    store.record(sid, discovery, 'day2-question', 'ask_expert', diagnosis['expert_question'], ['case-facts', 'handbook-v1'])
    answer = next(rule['expert_answer'] for rule in json.loads((ROOT / '03-scenarios/expert-only/rulebook.json').read_text())['rules'] if rule['family'] == 'substitution')
    draft = store.draft_card(sid, discovery, answer)
    published = store.review(sid, discovery, draft['card'], 'approve')
    fresh = store.start(sid, 'S02')
    fresh_card = '\n'.join(store.inspect(sid, fresh, 'approved-guidance')['content'])
    store.inspect(sid, fresh, 'case-facts')
    store.record(sid, fresh, 'day2-accept', 'accept', 'The approved card covers revision R2 with certificate C-B.', ['approved-guidance', 'case-facts'])
    fresh_result = store.state(sid)['attempts'][-1]['result']
    boundary = store.start(sid, 'S05')
    boundary_card = '\n'.join(store.inspect(sid, boundary, 'approved-guidance')['content'])
    store.inspect(sid, boundary, 'case-facts')
    store.record(sid, boundary, 'day2-reject', 'reject', 'Certificate C-A is outside the approved card.', ['approved-guidance', 'case-facts'])
    boundary_result = store.state(sid)['attempts'][-1]['result']
    boundary_action = store.state(sid)['attempts'][-1]['actions'][-1]['action']
    report = {
        'provider_model': diagnosis['model'],
        'spent_usd': round(store.spent(), 6),
        'diagnosis_category': diagnosis['category'],
        'diagnosis_action': diagnosis['suggested_action'],
        'diagnosis_question': diagnosis['expert_question'],
        'hidden_rule_leaked_into_question': leaks,
        'card_published': published['published'],
        'fresh_case_sees_card': draft['card'] in fresh_card,
        'fresh_case_correct': fresh_result['correct_action'],
        'fresh_case_independent': fresh_result['independent_completion'],
        'boundary_sees_card': 'C-B' in boundary_card,
        'boundary_action': boundary_action,
        'boundary_not_accepted': boundary_action != 'accept' and boundary_result['correct_action'],
    }
    (ROOT / '06-build' / 'day2-results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
