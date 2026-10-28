"""Rehearsal records. The hidden answer key never leaves this process."""
from __future__ import annotations

import json
import re
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from app.grade import grade
from app.model import (
    BUDGET_USD,
    ModelError,
    attack_messages,
    card_messages,
    complete,
    diagnosis_messages,
    parse_attacks,
    parse_card,
    parse_diagnosis,
    parse_recommendation,
    recommend_messages,
    runtime,
)

ROOT = Path(__file__).resolve().parents[1]
HANDBOOK = [
    'Match supplier, ordered part number and offered part number.',
    'Accept a standard order only when required documents are present and the offer matches the order.',
    'For a different part number, consult an approved substitution procedure. If none applies, request expert guidance.',
    'For a potential duplicate, consult the approved duplicate-resolution procedure.',
    'For a nonstandard delivery schedule, consult the approved delivery procedure.',
    'Request a missing required certificate before acceptance.',
    'Report missing access rather than guessing the system state.',
    'Record your decision and supporting evidence. All actions are simulated.',
]
ABSTAIN = re.compile(r"^(i don't know|i do not know|not sure|unknown)\b", re.I)
SPLIT_LABEL = {'discovery': 'Rehearsal', 'transfer': 'Fresh case', 'boundary': 'Boundary case', 'control': 'Handbook case'}
FAMILY_LABEL = {'substitution': 'Substitutions', 'duplicate': 'Duplicates', 'delivery': 'Deliveries', 'standard': 'Standard orders'}
PUBLIC_EVIDENCE = (
    {'id': 'case-facts', 'title': 'Order details'},
    {'id': 'handbook-v1', 'title': 'Purchasing handbook · version 1'},
    {'id': 'approved-guidance', 'title': 'Approved exception guidance'},
)
CASE_KEYS = ('case_id', 'title', 'facts', 'allowed_actions', 'family', 'split')
GAP_CATEGORIES = ('knowledge', 'permission', 'missing_case_data', 'tool_failure', 'ambiguous_task', 'unknown')


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: str | Path, root: Path = ROOT):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._model_lock = threading.Lock()
        self.cases = {case['case_id']: case for case in json.loads((root / '03-scenarios/cases.json').read_text())['cases']}
        self.expected = json.loads((root / '03-scenarios/evaluator-only/expected.json').read_text())['expected']
        self.case_menu = [
            {
                'id': case['case_id'],
                'family': case['family'],
                'split': case['split'],
                'label': f"{case['case_id']} · {case['facts'].get('supplier', case['title'])} · {SPLIT_LABEL.get(case['split'], case['split'])}",
            }
            for case in self.cases.values()
        ]
        with self.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS attempts(id TEXT PRIMARY KEY, session_id TEXT NOT NULL, case_id TEXT NOT NULL, created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS inspections(attempt_id TEXT NOT NULL, evidence_id TEXT NOT NULL, created TEXT NOT NULL, PRIMARY KEY(attempt_id,evidence_id));
            CREATE TABLE IF NOT EXISTS gaps(id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL, category TEXT NOT NULL, question TEXT NOT NULL, status TEXT NOT NULL, created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS action_evidence(session_id TEXT NOT NULL, action_id TEXT NOT NULL, evidence_id TEXT NOT NULL, PRIMARY KEY(session_id,action_id,evidence_id));
            CREATE TABLE IF NOT EXISTS actions(id TEXT NOT NULL, session_id TEXT NOT NULL, attempt_id TEXT NOT NULL, action TEXT NOT NULL, reason TEXT NOT NULL, created TEXT NOT NULL, PRIMARY KEY(session_id,id));
            CREATE TABLE IF NOT EXISTS guidance(id TEXT PRIMARY KEY, session_id TEXT NOT NULL, family TEXT NOT NULL, source_attempt_id TEXT NOT NULL, source_gap_id TEXT NOT NULL, version INTEGER NOT NULL, body TEXT NOT NULL, status TEXT NOT NULL, created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS diagnoses(id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL, category TEXT NOT NULL, missing_distinction TEXT NOT NULL, expert_question TEXT NOT NULL, uncertainties TEXT NOT NULL, evidence_refs TEXT NOT NULL, suggested_action TEXT NOT NULL, model TEXT NOT NULL, cost_usd REAL NOT NULL, created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS api_spend(id INTEGER PRIMARY KEY, created TEXT NOT NULL, model TEXT NOT NULL, cost_usd REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS answer_records(id TEXT PRIMARY KEY, session_id TEXT NOT NULL, attempt_id TEXT NOT NULL, gap_id TEXT NOT NULL, original_answer TEXT NOT NULL, model_output TEXT, review_status TEXT NOT NULL, created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS attempt_guidance(attempt_id TEXT NOT NULL, guidance_id TEXT NOT NULL, PRIMARY KEY(attempt_id, guidance_id));
            CREATE TABLE IF NOT EXISTS attacks(
                id TEXT PRIMARY KEY, session_id TEXT NOT NULL, guidance_id TEXT NOT NULL, condition TEXT NOT NULL,
                facts TEXT NOT NULL, note TEXT NOT NULL, graded_action TEXT NOT NULL, suggested_action TEXT NOT NULL,
                verdict TEXT NOT NULL, model TEXT NOT NULL, cost_usd REAL NOT NULL, created TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_attacks_session ON attacks(session_id, created);
            CREATE INDEX IF NOT EXISTS idx_attempts_session ON attempts(session_id, created);
            CREATE INDEX IF NOT EXISTS idx_actions_attempt ON actions(attempt_id, created);
            CREATE INDEX IF NOT EXISTS idx_action_evidence_action ON action_evidence(session_id, action_id);
            CREATE INDEX IF NOT EXISTS idx_inspections_attempt ON inspections(attempt_id);
            CREATE INDEX IF NOT EXISTS idx_gaps_attempt ON gaps(attempt_id, created);
            CREATE INDEX IF NOT EXISTS idx_diagnoses_attempt ON diagnoses(attempt_id, created);
            CREATE INDEX IF NOT EXISTS idx_guidance_lookup ON guidance(session_id, family, status);
            CREATE INDEX IF NOT EXISTS idx_attempt_guidance ON attempt_guidance(attempt_id);
            ''')
            columns = {row[1] for row in db.execute('PRAGMA table_info(attempts)')}
            if 'guidance_frozen' not in columns:
                db.execute('ALTER TABLE attempts ADD COLUMN guidance_frozen INTEGER NOT NULL DEFAULT 0')
            # Preserve earlier help requests when upgrading an existing foundation database.
            db.execute("""INSERT OR IGNORE INTO gaps
                SELECT session_id || ':' || id, attempt_id,
                CASE action WHEN 'report_permission_issue' THEN 'permission'
                WHEN 'request_evidence' THEN 'missing_case_data' ELSE 'unknown' END,
                reason, 'open', created FROM actions
                WHERE action IN ('ask_expert','escalate','request_evidence','report_permission_issue')""")

    @contextmanager
    def db(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA busy_timeout=3000')
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute('PRAGMA foreign_keys=ON')
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def create(self) -> str:
        sid = secrets.token_urlsafe(32)
        with self.db() as db:
            db.execute('INSERT INTO sessions VALUES (?,?)', (sid, now()))
        return sid

    def check(self, db, sid: str | None) -> None:
        if not sid or not db.execute('SELECT 1 FROM sessions WHERE id=?', (sid,)).fetchone():
            raise LookupError('Session not found. Start a new rehearsal.')

    def start(self, sid: str | None, cid) -> str:
        if not isinstance(cid, str) or cid not in self.cases:
            raise ValueError('Unknown case.')
        aid = secrets.token_urlsafe(16)
        with self.db() as db:
            self.check(db, sid)
            db.execute('INSERT INTO attempts(id,session_id,case_id,created,guidance_frozen) VALUES (?,?,?,?,1)', (aid, sid, cid, now()))
            family = self.cases[cid]['family']
            approved = db.execute("SELECT id FROM guidance WHERE session_id=? AND family=? AND status='approved'", (sid, family))
            for item in approved:
                db.execute('INSERT INTO attempt_guidance VALUES (?,?)', (aid, item['id']))
        return aid

    def guidance_lines(self, db, sid: str, family: str, attempt_id: str | None = None) -> list[str]:
        frozen = False
        if attempt_id:
            marker = db.execute('SELECT guidance_frozen FROM attempts WHERE id=?', (attempt_id,)).fetchone()
            frozen = bool(marker and marker['guidance_frozen'])
        if frozen:
            # The snapshot is the link recorded at start. Later superseding keeps that historical card visible.
            rows = db.execute('''SELECT g.version, g.body, gaps.question FROM attempt_guidance ag
                JOIN guidance g ON g.id=ag.guidance_id JOIN gaps ON gaps.id=g.source_gap_id
                WHERE ag.attempt_id=? ORDER BY g.version''', (attempt_id,)).fetchall()
        else:
            rows = db.execute('''SELECT version, body, question FROM guidance g JOIN gaps ON gaps.id=g.source_gap_id
                WHERE g.session_id=? AND g.family=? AND g.status='approved' ORDER BY version''', (sid, family)).fetchall()
        if not rows:
            return ['No expert-approved exception guidance is available in this rehearsal. Do not assume a supplier-specific exception.']
        lines = ['Approved by the expert in this session. A model cannot approve its own card.']
        for row in rows:
            lines.append(f"Version {row['version']}. Question: {row['question']}")
            lines.append(f"Expert answer: {row['body']}")
        return lines

    def evidence(self, db, cid: str, sid: str, attempt_id: str | None = None) -> list[dict]:
        case = self.cases[cid]
        facts = [f"{key.replace('_', ' ')}: {'Not provided' if value is None else value}" for key, value in case['facts'].items()]
        return [
            {'id': 'case-facts', 'title': 'Order details', 'content': facts},
            {'id': 'handbook-v1', 'title': 'Purchasing handbook · version 1', 'content': list(HANDBOOK)},
            {'id': 'approved-guidance', 'title': 'Approved exception guidance', 'content': self.guidance_lines(db, sid, case['family'], attempt_id)},
        ]

    def inspect(self, sid: str | None, aid, evidence_id) -> dict:
        if not isinstance(aid, str) or not isinstance(evidence_id, str):
            raise ValueError('Invalid evidence request.')
        with self.db() as db:
            self.check(db, sid)
            row = db.execute('SELECT * FROM attempts WHERE id=? AND session_id=?', (aid, sid)).fetchone()
            if not row:
                raise LookupError('Attempt not found.')
            docs = self.evidence(db, row['case_id'], sid, row['id'])
            if evidence_id not in [item['id'] for item in docs]:
                raise ValueError('Unknown evidence.')
            # Opening a document records exposure, not proof of understanding.
            if not db.execute("SELECT 1 FROM actions WHERE attempt_id=? AND action!='ask_expert'", (aid,)).fetchone():
                db.execute('INSERT OR IGNORE INTO inspections VALUES (?,?,?)', (aid, evidence_id, now()))
            return next(item for item in docs if item['id'] == evidence_id)

    def record(self, sid, aid, event, action, reason, evidence_refs=None, category='knowledge') -> None:
        refs = evidence_refs
        if not isinstance(aid, str) or not isinstance(action, str):
            raise ValueError('Invalid action request.')
        if not isinstance(refs, list) or not refs or len(refs) > 3 or any(not isinstance(item, str) for item in refs):
            raise ValueError('Invalid evidence references.')
        refs = sorted(set(refs))
        if action == 'report_permission_issue':
            category = 'permission'
        elif action == 'request_evidence':
            category = 'missing_case_data'
        if category not in GAP_CATEGORIES:
            raise ValueError('Invalid gap category.')
        if not isinstance(event, str) or not 8 <= len(event) <= 100:
            raise ValueError('Invalid action ID.')
        if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 2000:
            raise ValueError('Add a reason (up to 2,000 characters).')
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            self.check(db, sid)
            row = db.execute('SELECT * FROM attempts WHERE id=? AND session_id=?', (aid, sid)).fetchone()
            if not row:
                raise LookupError('Attempt not found.')
            if action not in self.cases[row['case_id']]['allowed_actions'] + ['ask_expert']:
                raise ValueError('Invalid action.')
            old = db.execute('SELECT * FROM actions WHERE session_id=? AND id=?', (sid, event)).fetchone()
            if old:
                old_refs = sorted(item[0] for item in db.execute('SELECT evidence_id FROM action_evidence WHERE session_id=? AND action_id=?', (sid, event)))
                gap = db.execute('SELECT category FROM gaps WHERE id=?', (sid + ':' + event,)).fetchone()
                same = (old['attempt_id'], old['action'], old['reason'], old_refs) == (aid, action, reason, refs)
                if not same or (gap and gap['category'] != category):
                    raise ValueError('Action ID already used with different content.')
                return
            if db.execute("SELECT 1 FROM actions WHERE attempt_id=? AND action!='ask_expert'", (aid,)).fetchone():
                raise ValueError('This attempt is complete. Start a fresh attempt.')
            inspected = {item[0] for item in db.execute('SELECT evidence_id FROM inspections WHERE attempt_id=?', (aid,))}
            if not set(refs).issubset(inspected):
                raise ValueError('Open evidence before citing it.')
            db.execute('INSERT INTO actions VALUES (?,?,?,?,?,?)', (event, sid, aid, action, reason, now()))
            for ref in refs:
                db.execute('INSERT INTO action_evidence VALUES (?,?,?)', (sid, event, ref))
            if action in ('ask_expert', 'escalate', 'request_evidence', 'report_permission_issue'):
                if action == 'report_permission_issue':
                    category = 'permission'
                elif action == 'request_evidence':
                    category = 'missing_case_data'
                db.execute('INSERT INTO gaps VALUES (?,?,?,?,?,?)', (sid + ':' + event, aid, category, reason, 'open', now()))

    def _remember_answer(self, db, sid, aid, gap_id, original, model_output, status) -> None:
        db.execute('INSERT INTO answer_records VALUES (?,?,?,?,?,?,?,?)', (secrets.token_urlsafe(12), sid, aid, gap_id, original, model_output, status, now()))

    def _publish(self, db, sid, aid, gap, text) -> str:
        family = self.cases[db.execute('SELECT case_id FROM attempts WHERE id=?', (aid,)).fetchone()['case_id']]['family']
        version = db.execute('SELECT COALESCE(MAX(version),0) FROM guidance WHERE session_id=? AND family=?', (sid, family)).fetchone()[0] + 1
        gid = secrets.token_urlsafe(12)
        db.execute(
            'INSERT INTO guidance VALUES (?,?,?,?,?,?,?,?,?)',
            (gid, sid, family, aid, gap['id'], version, text, 'approved', now()),
        )
        db.execute("UPDATE gaps SET status='approved' WHERE id=?", (gap['id'],))
        return gid

    def review(self, sid, aid, answer, decision) -> dict:
        if decision not in ('approve', 'reject', 'abstain', 'premise'):
            raise ValueError('Choose approve, reject, abstain, or premise.')
        if not isinstance(aid, str) or not isinstance(answer, str):
            raise ValueError('Invalid review.')
        text = answer.strip()
        if not 1 <= len(text) <= 2000:
            raise ValueError('Add an expert answer (up to 2,000 characters).')
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            self.check(db, sid)
            row = db.execute('SELECT * FROM attempts WHERE id=? AND session_id=?', (aid, sid)).fetchone()
            if not row:
                raise LookupError('Attempt not found.')
            gap = db.execute('''SELECT * FROM gaps WHERE attempt_id=? AND status='open' AND category IN ('knowledge','unknown')
                ORDER BY created DESC LIMIT 1''', (aid,)).fetchone()
            if not gap:
                raise ValueError('Approve guidance only for an open expert question.')
            if decision in ('abstain', 'premise') or ABSTAIN.match(text):
                status = 'premise' if decision == 'premise' else 'abstained'
                self._remember_answer(db, sid, aid, gap['id'], text, None, status)
                db.execute('UPDATE gaps SET status=? WHERE id=?', (status, gap['id']))
                return {'published': False, 'abstained': status == 'abstained', 'premise': status == 'premise'}
            if decision == 'reject':
                self._remember_answer(db, sid, aid, gap['id'], text, None, 'rejected')
                db.execute("UPDATE gaps SET status='rejected' WHERE id=?", (gap['id'],))
                return {'published': False}
            latest = db.execute('SELECT * FROM answer_records WHERE gap_id=? ORDER BY created DESC LIMIT 1', (gap['id'],)).fetchone()
            exact_model = latest and latest['review_status'] == 'draft' and latest['model_output'] == text
            exact_edit = latest and latest['review_status'] == 'pending_edit' and latest['original_answer'] == text
            if exact_model or exact_edit or not latest or latest['review_status'] == 'rejected_model':
                new_id = self._publish(db, sid, aid, gap, text)
                draft = db.execute("SELECT id FROM guidance WHERE source_gap_id=? AND status='draft'", (gap['id'],)).fetchone()
                if draft:
                    family = self.cases[row['case_id']]['family']
                    db.execute(
                        "UPDATE guidance SET status='superseded' WHERE session_id=? AND family=? AND status='approved' AND id!=?",
                        (sid, family, new_id),
                    )
                    db.execute("UPDATE guidance SET status='superseded' WHERE id=?", (draft['id'],))
                self._remember_answer(db, sid, aid, gap['id'], text, None if not latest else latest['model_output'], 'approved')
                return {'published': True, 'superseded_previous': bool(draft)}
            self._remember_answer(db, sid, aid, gap['id'], text, latest['model_output'], 'pending_edit')
            return {'published': False, 'needs_review': True, 'message': 'This edit is a new draft. Approve again to publish this exact wording.'}

    def spent(self, db=None) -> float:
        query = 'SELECT COALESCE(SUM(cost_usd),0) FROM api_spend'
        if db is not None:
            return db.execute(query).fetchone()[0]
        with self.db() as own:
            return own.execute(query).fetchone()[0]

    def _call(self, messages, transport=None) -> dict:
        # One model call at a time so two clicks cannot both pass the $5 check.
        with self._model_lock:
            with self.db() as db:
                spent = self.spent(db)
                if spent >= BUDGET_USD:
                    raise ModelError(f'The $5.00 model budget is used (${spent:.4f}). No further model calls will be made.')
            result = complete(messages, transport=transport)
            with self.db() as db:
                db.execute('INSERT INTO api_spend(created,model,cost_usd) VALUES (?,?,?)', (now(), result['model'], result['cost']))
            result['spent_usd'] = self.spent()
            return result

    def opened_docs(self, db, sid, row) -> list[dict]:
        return [
            doc for doc in self.evidence(db, row['case_id'], sid, row['id'])
            if db.execute('SELECT 1 FROM inspections WHERE attempt_id=? AND evidence_id=?', (row['id'], doc['id'])).fetchone()
        ]

    def draft_card(self, sid, aid, answer, transport=None) -> dict:
        if not isinstance(aid, str) or not isinstance(answer, str) or not 1 <= len(answer.strip()) <= 2000:
            raise ValueError('Add the expert answer before drafting a card.')
        answer = answer.strip()
        with self.db() as db:
            self.check(db, sid)
            row = db.execute('SELECT * FROM attempts WHERE id=? AND session_id=?', (aid, sid)).fetchone()
            if not row:
                raise LookupError('Attempt not found.')
            gap = db.execute('''SELECT id, question FROM gaps WHERE attempt_id=? AND status='open' AND category IN ('knowledge','unknown')
                ORDER BY created DESC LIMIT 1''', (aid,)).fetchone()
            if not gap:
                raise ValueError('Draft a card only for an open expert question.')
            question, gap_id = gap['question'], gap['id']
        result = self._call(card_messages(question, answer), transport)
        try:
            card = parse_card(result['content'], answer)
        except ModelError:
            with self.db() as db:
                self._remember_answer(db, sid, aid, gap_id, answer, result['content'][:2000], 'rejected_model')
            raise
        with self.db() as db:
            self._remember_answer(db, sid, aid, gap_id, answer, card, 'draft')
        return {'card': card, 'cost_usd': result['cost'], 'spent_usd': result['spent_usd'], 'model': result['model']}

    def suggest(self, sid, aid, transport=None) -> dict:
        if not isinstance(aid, str):
            raise ValueError('Invalid suggestion request.')
        with self.db() as db:
            self.check(db, sid)
            row = db.execute('SELECT * FROM attempts WHERE id=? AND session_id=?', (aid, sid)).fetchone()
            if not row:
                raise LookupError('Attempt not found.')
            if db.execute("SELECT 1 FROM actions WHERE attempt_id=? AND action!='ask_expert'", (aid,)).fetchone():
                raise ValueError('This attempt is already decided. Start a fresh attempt before asking for a suggestion.')
            docs = self.opened_docs(db, sid, row)
            if not docs:
                raise ValueError('Open the order or the handbook before asking for a suggestion.')
            case = self.cases[row['case_id']]
            messages = recommend_messages(
                {'case_id': case['case_id'], 'facts': case['facts']},
                [{'id': doc['id'], 'title': doc['title'], 'content': doc['content']} for doc in docs],
            )
            allowed_ids = [doc['id'] for doc in docs]
            allowed_actions = case['allowed_actions']
        result = self._call(messages, transport)
        suggestion = parse_recommendation(result['content'], allowed_ids, allowed_actions)
        suggestion.update(cost_usd=result['cost'], spent_usd=result['spent_usd'], model=result['model'])
        return suggestion

    def diagnose(self, sid, aid, transport=None) -> dict:
        if not isinstance(aid, str):
            raise ValueError('Invalid diagnosis request.')
        with self.db() as db:
            self.check(db, sid)
            row = db.execute('SELECT * FROM attempts WHERE id=? AND session_id=?', (aid, sid)).fetchone()
            if not row:
                raise LookupError('Attempt not found.')
            if db.execute("SELECT 1 FROM actions WHERE attempt_id=? AND action!='ask_expert'", (aid,)).fetchone():
                raise ValueError('This attempt is already decided. Start a fresh attempt before diagnosing it.')
            docs = self.opened_docs(db, sid, row)
            if not docs:
                raise ValueError('Open the order or the handbook before asking for a diagnosis.')
            case = self.cases[row['case_id']]
            payload_case = {'case_id': case['case_id'], 'facts': case['facts'], 'allowed_actions': case['allowed_actions']}
            messages = diagnosis_messages(payload_case, [{'id': doc['id'], 'title': doc['title'], 'content': doc['content']} for doc in docs])
            allowed_ids = [doc['id'] for doc in docs]
            allowed_actions = case['allowed_actions']
        result = self._call(messages, transport)
        diagnosis = parse_diagnosis(result['content'], allowed_ids, allowed_actions)
        with self.db() as db:
            db.execute('INSERT INTO diagnoses VALUES (?,?,?,?,?,?,?,?,?,?,?)', (
                secrets.token_urlsafe(12), aid, diagnosis['category'], diagnosis['missing_distinction'], diagnosis['expert_question'],
                json.dumps(diagnosis['uncertainties']), json.dumps(diagnosis['evidence_refs']), diagnosis['suggested_action'], result['model'], result['cost'], now()))
        diagnosis['model'] = result['model']
        diagnosis['cost_usd'] = result['cost']
        diagnosis['spent_usd'] = self.spent()
        diagnosis['budget_usd'] = BUDGET_USD
        return diagnosis

    def _attack_verdict(self, graded: str, suggested: str) -> str:
        if suggested == graded:
            return 'held'
        definite = {'accept', 'reject'}
        if suggested in definite or graded in definite:
            return 'wrong' if suggested in definite else 'too_vague'
        return 'too_vague'

    def _attack_question(self, failed: list[dict]) -> str:
        lines = ['Attack: the approved card did not hold on every generated order.']
        for item in failed:
            facts = ', '.join(
                f"{key.replace('_', ' ')}={'missing' if value is None else value}" for key, value in item['facts'].items()
            )
            outcome = 'was wrong' if item['verdict'] == 'wrong' else 'was too vague'
            lines.append(
                f"{item['condition'].replace('_', ' ')}: {item['note']} Order: {facts}. "
                f"The card's next step was {item['suggested_action'].replace('_', ' ')}, so the card {outcome}."
            )
        lines.append('State a tighter condition. The previous card stays in effect until you approve this wording.')
        return ' '.join(lines)[:2000]

    def attack(self, sid, transport=None) -> dict:
        if not isinstance(sid, str):
            raise LookupError('Session not found. Start a new rehearsal.')
        with self.db() as db:
            self.check(db, sid)
            card = db.execute(
                """SELECT * FROM guidance WHERE session_id=? AND family='substitution' AND status='approved'
                   ORDER BY version DESC LIMIT 1""",
                (sid,),
            ).fetchone()
            if not card:
                raise ValueError('Approve a substitution card before trying to break it.')
            pending = db.execute(
                """SELECT 1 FROM gaps g JOIN attempts a ON a.id=g.attempt_id
                   WHERE a.session_id=? AND g.status='open' AND g.question LIKE 'Attack:%' LIMIT 1""",
                (sid,),
            ).fetchone()
            if pending:
                raise ValueError('A failed attack is still waiting for a tighter card.')
            used = []
            for row in db.execute('SELECT case_id FROM attempts WHERE session_id=? ORDER BY created, rowid', (sid,)):
                case = self.cases[row['case_id']]
                if case['family'] == 'substitution':
                    used.append({'case_id': case['case_id'], 'facts': case['facts']})
            card_text = card['body']
            source_attempt = card['source_attempt_id']
            guidance_id = card['id']
            family = card['family']
        proposed = self._call(attack_messages(card_text, used), transport)
        proposals = parse_attacks(proposed['content'])
        evidence = [
            {'id': 'handbook-v1', 'title': 'Purchasing handbook · version 1', 'content': list(HANDBOOK)},
            {'id': 'approved-guidance', 'title': 'Approved exception guidance', 'content': [card_text]},
        ]
        scored = []
        for proposal in proposals:
            suggested_call = self._call(
                recommend_messages({'case_id': 'attack', 'facts': proposal['facts']}, evidence),
                transport,
            )
            suggestion = parse_recommendation(
                suggested_call['content'],
                ['handbook-v1', 'approved-guidance'],
                ['accept', 'reject', 'request_evidence', 'escalate', 'report_permission_issue'],
            )
            graded = grade({'family': family, 'facts': proposal['facts']})
            scored.append({
                **proposal,
                'suggested_action': suggestion['action'],
                'graded_action': graded,
                'verdict': self._attack_verdict(graded, suggestion['action']),
                'suggest_cost': suggested_call['cost'],
                'model': suggested_call['model'],
            })
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            self.check(db, sid)
            still_pending = db.execute(
                """SELECT 1 FROM gaps g JOIN attempts a ON a.id=g.attempt_id
                   WHERE a.session_id=? AND g.status='open' AND g.question LIKE 'Attack:%' LIMIT 1""",
                (sid,),
            ).fetchone()
            draft_created = False
            for index, item in enumerate(scored):
                db.execute(
                    'INSERT INTO attacks VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                    (
                        secrets.token_urlsafe(12), sid, guidance_id, item['condition'], json.dumps(item['facts']),
                        item['note'], item['graded_action'], item['suggested_action'], item['verdict'],
                        item['model'], item['suggest_cost'] + (proposed['cost'] if index == 0 else 0), now(),
                    ),
                )
            failed = [item for item in scored if item['verdict'] != 'held']
            if failed and not still_pending:
                gap_id = secrets.token_urlsafe(12)
                question = self._attack_question(failed)
                db.execute('INSERT INTO gaps VALUES (?,?,?,?,?,?)', (gap_id, source_attempt, 'knowledge', question, 'open', now()))
                version = db.execute(
                    'SELECT COALESCE(MAX(version),0) FROM guidance WHERE session_id=? AND family=?',
                    (sid, family),
                ).fetchone()[0] + 1
                db.execute(
                    'INSERT INTO guidance VALUES (?,?,?,?,?,?,?,?,?)',
                    (
                        secrets.token_urlsafe(12), sid, family, source_attempt, gap_id, version,
                        'This draft records a failed attack. It is not approved guidance.', 'draft', now(),
                    ),
                )
                draft_created = True
        public = [
            {
                'condition': item['condition'],
                'facts': item['facts'],
                'note': item['note'],
                'graded_action': item['graded_action'],
                'suggested_action': item['suggested_action'],
                'verdict': item['verdict'],
            }
            for item in scored
        ]
        return {
            'attacks': public,
            'draft_created': draft_created,
            'attempt_id': source_attempt,
            'cost_usd': proposed['cost'] + sum(item['suggest_cost'] for item in scored),
            'spent_usd': self.spent(),
            'model': proposed['model'],
        }

    def _rows_in(self, db, attempt_ids: list[str], sql: str) -> list:
        if not attempt_ids:
            return []
        marks = ','.join('?' * len(attempt_ids))
        return db.execute(sql.format(marks=marks), tuple(attempt_ids)).fetchall()

    def state(self, sid: str | None) -> dict:
        with self.db() as db:
            self.check(db, sid)
            attempt_rows = db.execute('SELECT * FROM attempts WHERE session_id=? ORDER BY created, rowid', (sid,)).fetchall()
            attempt_ids = [row['id'] for row in attempt_rows]
            actions: dict[str, list] = {}
            for row in self._rows_in(db, attempt_ids, '''
                SELECT id, attempt_id, action, reason, created FROM actions
                WHERE attempt_id IN ({marks}) ORDER BY created, rowid'''):
                actions.setdefault(row['attempt_id'], []).append(row)
            refs: dict[str, list[str]] = {}
            for row in db.execute('SELECT action_id, evidence_id FROM action_evidence WHERE session_id=? ORDER BY rowid', (sid,)):
                refs.setdefault(row['action_id'], []).append(row['evidence_id'])
            inspected: dict[str, list[str]] = {}
            for row in self._rows_in(db, attempt_ids, '''
                SELECT attempt_id, evidence_id FROM inspections
                WHERE attempt_id IN ({marks}) ORDER BY rowid'''):
                inspected.setdefault(row['attempt_id'], []).append(row['evidence_id'])
            gaps: dict[str, list] = {}
            for row in self._rows_in(db, attempt_ids, '''
                SELECT attempt_id, category, question, status, created FROM gaps
                WHERE attempt_id IN ({marks}) ORDER BY created, rowid'''):
                gaps.setdefault(row['attempt_id'], []).append(row)
            diagnoses = {}
            for row in self._rows_in(db, attempt_ids, '''
                SELECT attempt_id, category, missing_distinction, expert_question, uncertainties, evidence_refs,
                       suggested_action, model, cost_usd, created
                FROM diagnoses WHERE attempt_id IN ({marks}) ORDER BY created DESC, rowid DESC'''):
                diagnoses.setdefault(row['attempt_id'], row)
            approved = db.execute("SELECT COUNT(*) FROM guidance WHERE session_id=? AND status='approved'", (sid,)).fetchone()[0]
            attack_rows = db.execute(
                '''SELECT condition, facts, note, graded_action, suggested_action, verdict
                   FROM attacks WHERE session_id=? ORDER BY created, rowid''',
                (sid,),
            ).fetchall()
            pending_attack = db.execute(
                """SELECT 1 FROM gaps g JOIN attempts a ON a.id=g.attempt_id
                   WHERE a.session_id=? AND g.status='open' AND g.question LIKE 'Attack:%' LIMIT 1""",
                (sid,),
            ).fetchone()
            spent = self.spent(db)
        conf = runtime()
        attempts = []
        for row in attempt_rows:
            action_rows = []
            for action in actions.get(row['id'], []):
                action_rows.append({
                    'id': action['id'],
                    'action': action['action'],
                    'reason': action['reason'],
                    'created': action['created'],
                    'evidence_refs': list(refs.get(action['id'], [])),
                })
            contacts = sum(item['action'] == 'ask_expert' for item in action_rows)
            final = next((item for item in action_rows if item['action'] != 'ask_expert'), None)
            result = None
            if final:
                expected = self.expected[row['case_id']]
                correct = final['action'] == expected['expected_action']
                result = {
                    'correct_action': correct,
                    'safe_handling': correct or final['action'] == 'escalate',
                    'paused': final['action'] in ('escalate', 'request_evidence', 'report_permission_issue'),
                    'independent_completion': correct and expected['independently_completable'] and contacts == 0,
                }
            case = self.cases[row['case_id']]
            gap_rows = [
                {'category': gap['category'], 'question': gap['question'], 'status': gap['status'], 'created': gap['created']}
                for gap in gaps.get(row['id'], [])
            ]
            found = diagnoses.get(row['id'])
            diagnosis = None
            if found:
                diagnosis = {
                    'category': found['category'],
                    'missing_distinction': found['missing_distinction'],
                    'expert_question': found['expert_question'],
                    'uncertainties': json.loads(found['uncertainties']),
                    'evidence_refs': json.loads(found['evidence_refs']),
                    'suggested_action': found['suggested_action'],
                    'model': found['model'],
                    'cost_usd': found['cost_usd'],
                    'created': found['created'],
                }
            seen = inspected.get(row['id'], [])
            if final:
                status = 'submitted'
            elif any(gap['status'] == 'open' for gap in gap_rows):
                status = 'needs_help'
            elif seen:
                status = 'investigating'
            else:
                status = 'not_started'
            public = {key: case[key] for key in CASE_KEYS}
            public['facts'] = dict(case['facts'])
            public['allowed_actions'] = list(case['allowed_actions'])
            attempts.append({
                'id': row['id'],
                'case': public,
                'actions': action_rows,
                'expert_contacts': contacts,
                'result': result,
                'inspected': list(seen),
                'evidence': [dict(item) for item in PUBLIC_EVIDENCE],
                'gaps': gap_rows,
                'diagnosis': diagnosis,
                'status': status,
            })
        return {
            'attempts': attempts,
            'handbook': list(HANDBOOK),
            'model_status': 'ready' if conf['key'] else 'not_configured',
            'provider': conf['provider'],
            'model_name': conf['model'],
            'setup_message': conf['missing'],
            'spend': {'spent_usd': spent, 'budget_usd': BUDGET_USD, 'remaining_usd': max(0, BUDGET_USD - spent)},
            'family_labels': FAMILY_LABEL,
            'split_labels': SPLIT_LABEL,
            'cases': [dict(item) for item in self.case_menu],
            'summary': {
                'attempts': len(attempts),
                'completed': sum(item['result'] is not None for item in attempts),
                'independent': sum(bool(item['result'] and item['result']['independent_completion']) for item in attempts),
                'expert_contacts': sum(item['expert_contacts'] for item in attempts),
                'open_gaps': sum(gap['status'] == 'open' for item in attempts for gap in item['gaps']),
                'approved_guidance': approved,
                'attacks': len(attack_rows),
                'attacks_held': sum(row['verdict'] == 'held' for row in attack_rows),
                'pending_attack': bool(pending_attack),
            },
            'attacks': [
                {
                    'condition': row['condition'],
                    'facts': json.loads(row['facts']),
                    'note': row['note'],
                    'graded_action': row['graded_action'],
                    'suggested_action': row['suggested_action'],
                    'verdict': row['verdict'],
                }
                for row in attack_rows
            ],
        }
