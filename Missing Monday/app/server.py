"""Local Missing Monday rehearsal. Meta diagnoses a stall; it does not grade the case."""
import argparse
import json
import re
from contextlib import contextmanager
import secrets
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from app.model import BUDGET_USD, ModelError, card_messages, complete, diagnosis_messages, parse_card, parse_diagnosis, parse_recommendation, recommend_messages, runtime

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / 'app/static'
HANDBOOK = [
    'Match supplier, ordered part number and offered part number.',
    'Accept a standard order only when required documents are present and the offer matches the order.',
    'For a different part number, consult an approved substitution procedure. If none applies, request expert guidance.',
    'For a potential duplicate, consult the approved duplicate-resolution procedure.',
    'For a nonstandard delivery schedule, consult the approved delivery procedure.',
    'Request a missing required certificate before acceptance.',
    'Report missing access rather than guessing the system state.',
    'Record your decision and supporting evidence. All actions are simulated.'
]
ABSTAIN = re.compile(r"^(i don't know|i do not know|not sure|unknown)\b", re.I)
SPLIT_LABEL = {'discovery': 'Rehearsal', 'transfer': 'Fresh case', 'boundary': 'Boundary case', 'control': 'Handbook case'}
FAMILY_LABEL = {'substitution': 'Substitutions', 'duplicate': 'Duplicates', 'delivery': 'Deliveries', 'standard': 'Standard orders'}

def now():
    return datetime.now(timezone.utc).isoformat()

class Store:
    def __init__(self, path, root=ROOT):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.cases = {c['case_id']: c for c in json.loads((root/'03-scenarios/cases.json').read_text())['cases']}
        self.expected = json.loads((root/'03-scenarios/evaluator-only/expected.json').read_text())['expected']
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
            ''')
            columns={row[1] for row in db.execute('PRAGMA table_info(attempts)')}
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
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()
    def create(self):
        sid = secrets.token_urlsafe(32)
        with self.db() as db:
            db.execute('INSERT INTO sessions VALUES (?,?)', (sid,now()))
        return sid
    def check(self, db, sid):
        if not sid or not db.execute('SELECT 1 FROM sessions WHERE id=?',(sid,)).fetchone():
            raise LookupError('Session not found. Start a new rehearsal.')
    def start(self, sid, cid):
        if not isinstance(cid,str) or cid not in self.cases: raise ValueError('Unknown case.')
        aid = secrets.token_urlsafe(16)
        with self.db() as db:
            self.check(db,sid)
            db.execute('INSERT INTO attempts(id,session_id,case_id,created,guidance_frozen) VALUES (?,?,?,?,1)',(aid,sid,cid,now()))
            family=self.cases[cid]['family']
            for item in db.execute("SELECT id FROM guidance WHERE session_id=? AND family=? AND status='approved'",(sid,family)):
                db.execute('INSERT INTO attempt_guidance VALUES (?,?)',(aid,item['id']))
        return aid
    def guidance_lines(self, db, sid, family, attempt_id=None):
        frozen=False
        if attempt_id:
            marker=db.execute('SELECT guidance_frozen FROM attempts WHERE id=?',(attempt_id,)).fetchone()
            frozen=bool(marker and marker['guidance_frozen'])
        if frozen:
            rows=db.execute('''SELECT g.version, g.body, gaps.question FROM attempt_guidance ag
                JOIN guidance g ON g.id=ag.guidance_id JOIN gaps ON gaps.id=g.source_gap_id
                WHERE ag.attempt_id=? AND g.status='approved' ORDER BY g.version''',(attempt_id,)).fetchall()
        else:
            rows=db.execute('''SELECT version, body, question FROM guidance g JOIN gaps ON gaps.id=g.source_gap_id
                WHERE g.session_id=? AND g.family=? AND g.status='approved' ORDER BY version''',(sid,family)).fetchall()
        if not rows:
            return ['No expert-approved exception guidance is available in this rehearsal. Do not assume a supplier-specific exception.']
        lines=['Approved by the expert in this session. A model cannot approve its own card.']
        for row in rows:
            lines.append(f"Version {row['version']}. Question: {row['question']}")
            lines.append(f"Expert answer: {row['body']}")
        return lines
    def evidence(self, db, cid, sid, attempt_id=None):
        case=self.cases[cid]
        return [dict(id='case-facts', title='Order details', content=[f"{k.replace('_',' ')}: {'Not provided' if v is None else v}" for k,v in case['facts'].items()]),
                dict(id='handbook-v1',title='Purchasing handbook · version 1',content=HANDBOOK),
                dict(id='approved-guidance',title='Approved exception guidance',content=self.guidance_lines(db,sid,case['family'],attempt_id))]

    def inspect(self,sid,aid,evidence_id):
        if not isinstance(aid,str) or not isinstance(evidence_id,str): raise ValueError('Invalid evidence request.')
        with self.db() as db:
            self.check(db,sid)
            row=db.execute('SELECT * FROM attempts WHERE id=? AND session_id=?',(aid,sid)).fetchone()
            if not row: raise LookupError('Attempt not found.')
            docs=self.evidence(db,row['case_id'],sid,row['id'])
            if evidence_id not in [e['id'] for e in docs]: raise ValueError('Unknown evidence.')
            # Opening a document records exposure, not proof of understanding.
            if not db.execute("SELECT 1 FROM actions WHERE attempt_id=? AND action!='ask_expert'",(aid,)).fetchone():
                db.execute('INSERT OR IGNORE INTO inspections VALUES (?,?,?)',(aid,evidence_id,now()))
            return next(e for e in docs if e['id']==evidence_id)

    def record(self,sid,aid,event,action,reason,evidence_refs=None,category='knowledge'):
        refs=evidence_refs
        if not isinstance(aid,str) or not isinstance(action,str): raise ValueError('Invalid action request.')
        categories=('knowledge','permission','missing_case_data','tool_failure','ambiguous_task','unknown')
        if not isinstance(refs,list) or not refs or len(refs)>3 or any(not isinstance(x,str) for x in refs): raise ValueError('Invalid evidence references.')
        refs=sorted(set(refs))
        if action=='report_permission_issue': category='permission'
        elif action=='request_evidence': category='missing_case_data'
        if category not in categories: raise ValueError('Invalid gap category.')
        if not isinstance(event,str) or not 8 <= len(event) <= 100: raise ValueError('Invalid action ID.')
        if not isinstance(reason,str) or not 1 <= len(reason.strip()) <= 2000: raise ValueError('Add a reason (up to 2,000 characters).')
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            self.check(db,sid)
            row=db.execute('SELECT * FROM attempts WHERE id=? AND session_id=?',(aid,sid)).fetchone()
            if not row: raise LookupError('Attempt not found.')
            if action not in self.cases[row['case_id']]['allowed_actions'] + ['ask_expert']: raise ValueError('Invalid action.')
            old=db.execute('SELECT * FROM actions WHERE session_id=? AND id=?',(sid,event)).fetchone()
            if old:
                oldrefs=sorted(a[0] for a in db.execute('SELECT evidence_id FROM action_evidence WHERE session_id=? AND action_id=?',(sid,event)))
                gap=db.execute('SELECT category FROM gaps WHERE id=?',(sid+':'+event,)).fetchone()
                if (old['attempt_id'],old['action'],old['reason'],oldrefs) != (aid,action,reason,refs) or (gap and gap['category']!=category): raise ValueError('Action ID already used with different content.')
                return
            if db.execute("SELECT 1 FROM actions WHERE attempt_id=? AND action!='ask_expert'",(aid,)).fetchone(): raise ValueError('This attempt is complete. Start a fresh attempt.')
            inspected={a[0] for a in db.execute('SELECT evidence_id FROM inspections WHERE attempt_id=?',(aid,))}
            if not set(refs).issubset(inspected): raise ValueError('Open evidence before citing it.')
            if not refs: raise ValueError('Select at least one inspected source.')
            db.execute('INSERT INTO actions VALUES (?,?,?,?,?,?)',(event,sid,aid,action,reason,now()))
            for ref in refs: db.execute('INSERT INTO action_evidence VALUES (?,?,?)',(sid,event,ref))
            if action in ('ask_expert','escalate','request_evidence','report_permission_issue'):
                if action=='report_permission_issue': category='permission'
                elif action=='request_evidence': category='missing_case_data'
                db.execute('INSERT INTO gaps VALUES (?,?,?,?,?,?)',(sid+':'+event,aid,category,reason,'open',now()))

    def _remember_answer(self, db, sid, aid, gap_id, original, model_output, status):
        db.execute('INSERT INTO answer_records VALUES (?,?,?,?,?,?,?,?)',(secrets.token_urlsafe(12),sid,aid,gap_id,original,model_output,status,now()))
    def _publish(self, db, sid, aid, gap, text):
        family=self.cases[db.execute('SELECT case_id FROM attempts WHERE id=?',(aid,)).fetchone()['case_id']]['family']
        version=db.execute('SELECT COALESCE(MAX(version),0) FROM guidance WHERE session_id=? AND family=?',(sid,family)).fetchone()[0]+1
        db.execute('INSERT INTO guidance VALUES (?,?,?,?,?,?,?,?,?)',(secrets.token_urlsafe(12),sid,family,aid,gap['id'],version,text,'approved',now()))
        db.execute("UPDATE gaps SET status='approved' WHERE id=?",(gap['id'],))
    def review(self,sid,aid,answer,decision):
        if decision not in ('approve','reject','abstain','premise'): raise ValueError('Choose approve, reject, abstain, or premise.')
        if not isinstance(aid,str) or not isinstance(answer,str): raise ValueError('Invalid review.')
        text=answer.strip()
        if not 1<=len(text)<=2000: raise ValueError('Add an expert answer (up to 2,000 characters).')
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            self.check(db,sid)
            row=db.execute('SELECT * FROM attempts WHERE id=? AND session_id=?',(aid,sid)).fetchone()
            if not row: raise LookupError('Attempt not found.')
            gap=db.execute('''SELECT * FROM gaps WHERE attempt_id=? AND status='open' AND category IN ('knowledge','unknown')
                ORDER BY created DESC LIMIT 1''',(aid,)).fetchone()
            if not gap: raise ValueError('Approve guidance only for an open expert question.')
            if decision in ('abstain','premise') or ABSTAIN.match(text):
                status='premise' if decision=='premise' else 'abstained'
                self._remember_answer(db,sid,aid,gap['id'],text,None,status)
                db.execute('UPDATE gaps SET status=? WHERE id=?',(status,gap['id']))
                return {'published':False,'abstained':status=='abstained','premise':status=='premise'}
            if decision=='reject':
                self._remember_answer(db,sid,aid,gap['id'],text,None,'rejected')
                db.execute("UPDATE gaps SET status='rejected' WHERE id=?",(gap['id'],))
                return {'published':False}
            latest=db.execute('SELECT * FROM answer_records WHERE gap_id=? ORDER BY created DESC LIMIT 1',(gap['id'],)).fetchone()
            exact_model=latest and latest['review_status']=='draft' and latest['model_output']==text
            exact_edit=latest and latest['review_status']=='pending_edit' and latest['original_answer']==text
            if exact_model or exact_edit or not latest or latest['review_status']=='rejected_model':
                self._publish(db,sid,aid,gap,text)
                self._remember_answer(db,sid,aid,gap['id'],text,None if not latest else latest['model_output'],'approved')
                return {'published':True}
            self._remember_answer(db,sid,aid,gap['id'],text,latest['model_output'],'pending_edit')
            return {'published':False,'needs_review':True,'message':'This edit is a new draft. Approve again to publish this exact wording.'}

    def spent(self, db=None):
        query = "SELECT COALESCE(SUM(cost_usd),0) FROM api_spend"
        if db is not None:
            return db.execute(query).fetchone()[0]
        with self.db() as own:
            return own.execute(query).fetchone()[0]

    def _call(self, messages, transport=None):
        with self.db() as db:
            spent = self.spent(db)
            if spent >= BUDGET_USD:
                raise ModelError(f'The $5.00 model budget is used (${spent:.4f}). No further model calls will be made.')
        result = complete(messages, transport=transport)
        with self.db() as db:
            db.execute('INSERT INTO api_spend(created,model,cost_usd) VALUES (?,?,?)', (now(), result['model'], result['cost']))
        result['spent_usd'] = self.spent()
        return result

    def opened_docs(self, db, sid, row):
        return [doc for doc in self.evidence(db, row['case_id'], sid, row['id']) if db.execute('SELECT 1 FROM inspections WHERE attempt_id=? AND evidence_id=?', (row['id'], doc['id'])).fetchone()]

    def draft_card(self, sid, aid, answer, transport=None):
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

    def suggest(self, sid, aid, transport=None):
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
            messages = recommend_messages({'case_id': case['case_id'], 'facts': case['facts']}, [{'id': doc['id'], 'title': doc['title'], 'content': doc['content']} for doc in docs])
            allowed_ids = [doc['id'] for doc in docs]
            allowed_actions = case['allowed_actions']
        result = self._call(messages, transport)
        suggestion = parse_recommendation(result['content'], allowed_ids, allowed_actions)
        suggestion.update(cost_usd=result['cost'], spent_usd=result['spent_usd'], model=result['model'])
        return suggestion

    def diagnose(self, sid, aid, transport=None):
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

    def state(self,sid):
        with self.db() as db:
            self.check(db,sid)
            attempts=[]
            for row in db.execute('SELECT * FROM attempts WHERE session_id=? ORDER BY created',(sid,)):
                actions=[dict(a) for a in db.execute('SELECT id,action,reason,created FROM actions WHERE attempt_id=? ORDER BY created',(row['id'],))]
                for a in actions:
                    a['evidence_refs']=[e[0] for e in db.execute('SELECT evidence_id FROM action_evidence WHERE session_id=? AND action_id=?',(sid,a['id']))]
                contacts=sum(a['action']=='ask_expert' for a in actions)
                final=next((a for a in actions if a['action']!='ask_expert'),None)
                result=None
                if final:
                    expected=self.expected[row['case_id']]
                    correct=final['action']==expected['expected_action']
                    safe=correct or final['action']=='escalate'
                    result=dict(correct_action=correct,safe_handling=safe,paused=final['action'] in ('escalate','request_evidence','report_permission_issue'),independent_completion=correct and expected['independently_completable'] and contacts==0)
                c=self.cases[row['case_id']]
                inspected=[e[0] for e in db.execute('SELECT evidence_id FROM inspections WHERE attempt_id=?',(row['id'],))]
                gaps=[dict(g) for g in db.execute('SELECT category,question,status,created FROM gaps WHERE attempt_id=? ORDER BY created',(row['id'],))]
                found=db.execute('SELECT category,missing_distinction,expert_question,uncertainties,evidence_refs,suggested_action,model,cost_usd,created FROM diagnoses WHERE attempt_id=? ORDER BY created DESC LIMIT 1',(row['id'],)).fetchone()
                diagnosis=None
                if found:
                    diagnosis=dict(found)
                    diagnosis['uncertainties']=json.loads(diagnosis['uncertainties'])
                    diagnosis['evidence_refs']=json.loads(diagnosis['evidence_refs'])
                status='submitted' if final else 'needs_help' if any(g['status']=='open' for g in gaps) else 'investigating' if inspected else 'not_started'
                attempts.append(dict(id=row['id'],case={k:c[k] for k in ('case_id','title','facts','allowed_actions','family','split')},actions=actions,expert_contacts=contacts,result=result,inspected=inspected,evidence=[dict(id=e['id'],title=e['title']) for e in self.evidence(db,c['case_id'],sid,row['id'])],gaps=gaps,diagnosis=diagnosis,status=status))
            approved=db.execute("SELECT COUNT(*) FROM guidance WHERE session_id=? AND status='approved'",(sid,)).fetchone()[0]
            spent=self.spent(db)
            conf=runtime()
        return dict(attempts=attempts,handbook=HANDBOOK,model_status='ready' if conf['key'] else 'not_configured',provider=conf['provider'],model_name=conf['model'],setup_message=conf['missing'],spend=dict(spent_usd=spent,budget_usd=BUDGET_USD,remaining_usd=max(0,BUDGET_USD-spent)),family_labels=FAMILY_LABEL,split_labels=SPLIT_LABEL,cases=[dict(id=c['case_id'],family=c['family'],split=c['split'],label=f"{c['case_id']} · {c['facts'].get('supplier',c['title'])} · {SPLIT_LABEL.get(c['split'],c['split'])}") for c in self.cases.values()],summary=dict(attempts=len(attempts),completed=sum(a['result'] is not None for a in attempts),independent=sum(bool(a['result'] and a['result']['independent_completion']) for a in attempts),expert_contacts=sum(a['expert_contacts'] for a in attempts),open_gaps=sum(g['status']=='open' for a in attempts for g in a['gaps']),approved_guidance=approved))

def handler(store, port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def send(self,status,data,kind='application/json'):
            raw=json.dumps(data).encode() if kind=='application/json' else data
            self.send_response(status)
            self.send_header('Content-Type',kind)
            self.send_header('Content-Length',str(len(raw)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'")
            self.end_headers();self.wfile.write(raw)
        def valid_host(self):
            return self.headers.get('Host') in (f'127.0.0.1:{port}',f'localhost:{port}')
        def do_GET(self):
            if not self.valid_host(): return self.send(403,{'error':'Local access only.'})
            path=urlsplit(self.path).path
            if path=='/health':
                conf=runtime()
                return self.send(200,{'status':'ok','model':'ready' if conf['key'] else 'not_configured','provider':conf['provider'],'model_name':conf['model'],'budget_usd':BUDGET_USD,'spent_usd':store.spent()})
            if path=='/api/state':
                try: return self.send(200,store.state(self.headers.get('X-Session-ID')))
                except LookupError as e: return self.send(404,{'error':str(e)})
            assets={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/app.css':('app.css','text/css; charset=utf-8')}
            if path not in assets: return self.send(404,{'error':'Not found.'})
            name,kind=assets[path];self.send(200,(STATIC/name).read_bytes(),kind)
        def do_POST(self):
            if not self.valid_host(): return self.send(403,{'error':'Local access only.'})
            origin=self.headers.get('Origin')
            if origin and origin not in (f'http://127.0.0.1:{port}',f'http://localhost:{port}'):
                return self.send(403,{'error':'Cross-origin request blocked.'})
            if self.headers.get('Content-Type','').split(';')[0]!='application/json': return self.send(415,{'error':'JSON required.'})
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=10000: raise ValueError('Invalid request size.')
                body=json.loads(self.rfile.read(size))
                if not isinstance(body,dict): raise ValueError('JSON object required.')
                sid=self.headers.get('X-Session-ID')
                path=urlsplit(self.path).path
                if path=='/api/sessions': return self.send(201,{'session_id':store.create()})
                if path=='/api/attempts': return self.send(201,{'attempt_id':store.start(sid,body.get('case_id'))})
                if path=='/api/inspect':
                    return self.send(200,store.inspect(sid,body.get('attempt_id'),body.get('evidence_id')))
                if path=='/api/actions':
                    store.record(sid,body.get('attempt_id'),body.get('id'),body.get('action'),body.get('reason'),body.get('evidence_refs',[]),body.get('category','knowledge'))
                    return self.send(200,{'saved':True})
                if path=='/api/guidance':
                    return self.send(200,store.review(sid,body.get('attempt_id'),body.get('answer'),body.get('decision')))
                if path=='/api/diagnose':
                    return self.send(200,store.diagnose(sid,body.get('attempt_id')))
                if path=='/api/draft':
                    return self.send(200,store.draft_card(sid,body.get('attempt_id'),body.get('answer')))
                if path=='/api/suggest':
                    return self.send(200,store.suggest(sid,body.get('attempt_id')))
                return self.send(404,{'error':'Not found.'})
            except LookupError as e: self.send(404,{'error':str(e)})
            except ModelError as e: self.send(502,{'error':str(e)})
            except (ValueError,TypeError) as e: self.send(400,{'error':str(e)})
            except Exception: self.send(500,{'error':'Could not save this request. Please retry.'})
    return Handler

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8766)
    parser.add_argument('--db',default=str(ROOT/'runs/missing-monday.sqlite3'))
    args=parser.parse_args()
    store=Store(args.db)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),handler(store,args.port))
    print(f'Missing Monday: http://127.0.0.1:{args.port}',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
if __name__=='__main__': main()
