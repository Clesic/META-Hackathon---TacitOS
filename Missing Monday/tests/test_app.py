import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
from app.model import ModelError
from app.server import Store,handler,ROOT

class FoundationTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.store=Store(Path(self.tmp.name)/'test.sqlite3');self.sid=self.store.create()
 def record(self,*args):
  if len(args)==5:
   sid,aid,event,action,reason=args
   self.store.inspect(sid,aid,'case-facts')
   args=(*args,['case-facts'])
  return self.store.record(*args)
 def tearDown(self): self.tmp.cleanup()
 def test_outcomes_all_fixtures(self):
  for cid, exp in self.store.expected.items():
   aid=self.store.start(self.sid,cid)
   self.record(self.sid,aid,'event-'+cid,exp['expected_action'],'Synthetic fixture test')
   last=self.store.state(self.sid)['attempts'][-1]
   self.assertTrue(last['result']['correct_action'])
   self.assertEqual(last['result']['independent_completion'],exp['independently_completable'])
 def test_help_prevents_independent_completion(self):
  aid=self.store.start(self.sid,'S01')
  self.record(self.sid,aid,'help-0001','ask_expert','Need substitution rule')
  self.record(self.sid,aid,'final-001','accept','Expert helped')
  self.assertFalse(self.store.state(self.sid)['attempts'][0]['result']['independent_completion'])
 def test_idempotent_and_conflicting_retry(self):
  aid=self.store.start(self.sid,'S01')
  for _ in range(2): self.record(self.sid,aid,'help-0001','ask_expert','Need rule')
  self.assertEqual(self.store.state(self.sid)['summary']['expert_contacts'],1)
  with self.assertRaises(ValueError): self.record(self.sid,aid,'help-0001','accept','Changed')
 def test_terminal_attempt_and_session_isolation(self):
  aid=self.store.start(self.sid,'S01');other=self.store.create()
  with self.assertRaises(LookupError): self.record(other,aid,'other-001','accept','No access')
  self.record(self.sid,aid,'final-001','accept','My decision')
  with self.assertRaises(ValueError): self.record(self.sid,aid,'final-002','reject','Changed decision')
 def test_persistence_and_no_oracle_fields(self):
  self.store.start(self.sid,'S01')
  state=Store(self.store.path).state(self.sid)
  self.assertEqual(len(state['attempts']),1)
  self.assertEqual([item['id'] for item in state['attempts'][0]['evidence']], ['case-facts','handbook-v1','approved-guidance'])
  encoded=json.dumps(state)
  for forbidden in ['expected_action','accept_if','expert_answer','independently_completable']:
   self.assertNotIn(forbidden,encoded)
 def test_wrong_action_and_safe_escalation(self):
  self.record(self.sid,self.store.start(self.sid,'S04'),'wrong-001','accept','Guess')
  r=self.store.state(self.sid)['attempts'][-1]['result'];self.assertFalse(r['correct_action']);self.assertFalse(r['safe_handling'])
  self.record(self.sid,self.store.start(self.sid,'S01'),'safe-0001','escalate','Rule missing')
  r=self.store.state(self.sid)['attempts'][-1]['result'];self.assertTrue(r['safe_handling']);self.assertFalse(r['independent_completion'])
 def test_evidence_is_required_and_must_be_opened(self):
  aid=self.store.start(self.sid,'S01')
  with self.assertRaises(ValueError): self.record(self.sid,aid,'event-0001','accept','A reason',[])
  with self.assertRaises(ValueError): self.record(self.sid,aid,'event-0001','accept','A reason',['handbook-v1'])
  doc=self.store.inspect(self.sid,aid,'handbook-v1')
  self.assertEqual(doc['id'],'handbook-v1')
  self.record(self.sid,aid,'event-0001','ask_expert','Which revision allows this alternative?',['handbook-v1'])
  state=Store(self.store.path).state(self.sid)['attempts'][0]
  self.assertEqual(state['actions'][0]['evidence_refs'],['handbook-v1'])
  self.assertEqual(state['gaps'][0]['question'],'Which revision allows this alternative?')
  self.assertEqual(state['status'],'needs_help')
 def test_inspection_is_scoped_and_idempotent(self):
  aid=self.store.start(self.sid,'S01')
  with self.assertRaises(LookupError): self.store.inspect(self.store.create(),aid,'handbook-v1')
  with self.assertRaises(ValueError): self.store.inspect(self.sid,aid,'rulebook')
  self.store.inspect(self.sid,aid,'handbook-v1');self.store.inspect(self.sid,aid,'handbook-v1')
  self.assertEqual(self.store.state(self.sid)['attempts'][0]['inspected'],['handbook-v1'])
 def test_missing_evidence_gap_retry(self):
  aid=self.store.start(self.sid,'S06');self.store.inspect(self.sid,aid,'case-facts')
  for _ in range(2): self.record(self.sid,aid,'event-0001','request_evidence','Need certificate',['case-facts'])
  state=self.store.state(self.sid)['attempts'][0]
  self.assertEqual(len(state['gaps']),1)
  self.assertEqual(state['gaps'][0]['category'],'missing_case_data')
  self.assertFalse(state['result']['independent_completion'])
 def test_null_evidence_cannot_bypass_validation(self):
  aid=self.store.start(self.sid,'S01')
  for refs in (None,[],{},'handbook-v1'):
   with self.assertRaises(ValueError): self.store.record(self.sid,aid,'null-0001','accept','Bypass attempt',refs)
  self.assertEqual(self.store.state(self.sid)['attempts'][0]['actions'],[])
 def test_unnecessary_evidence_is_not_successful_handling(self):
  aid=self.store.start(self.sid,'C01')
  self.record(self.sid,aid,'extra-001','request_evidence','Ask for documents that already exist')
  result=self.store.state(self.sid)['attempts'][0]['result']
  self.assertFalse(result['safe_handling']);self.assertTrue(result['paused'])
 def test_reviewing_completed_attempt_does_not_change_exposure(self):
  aid=self.store.start(self.sid,'C01')
  self.record(self.sid,aid,'done-0001','accept','Matches handbook')
  before=self.store.state(self.sid)['attempts'][0]['inspected']
  self.store.inspect(self.sid,aid,'handbook-v1')
  self.assertEqual(before,self.store.state(self.sid)['attempts'][0]['inspected'])
 def test_malformed_case_and_attempt_ids(self):
  with self.assertRaises(ValueError):self.store.start(self.sid,[])
  with self.assertRaises(ValueError):self.store.inspect(self.sid,{},'handbook-v1')
 def test_http_boundaries(self):
  server=ThreadingHTTPServer(('127.0.0.1',0),handler(self.store,0))
  port=server.server_port;server.RequestHandlerClass=handler(self.store,port)
  thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  base=f'http://127.0.0.1:{port}'
  try:
   with urlopen(base+'/health') as response:
    body=json.load(response)
    self.assertEqual(body['status'],'ok')
    self.assertEqual(set(body), {'status','model','provider','model_name','budget_usd','spent_usd'})
    self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
    self.assertEqual(response.headers['Referrer-Policy'], 'no-referrer')
    self.assertEqual(response.headers['X-Frame-Options'], 'DENY')
    self.assertIn("frame-ancestors 'none'", response.headers['Content-Security-Policy'])
    self.assertNotIn('unsafe-inline', response.headers['Content-Security-Policy'])
   with urlopen(base+'/favicon.svg') as response:
    self.assertEqual(response.status, 200)
    self.assertIn('image/svg+xml', response.headers['Content-Type'])
   for path in ['/03-scenarios/expert-only/rulebook.json','/../.env','/app/server.py','/api/state']:
    with self.assertRaises(HTTPError) as e:urlopen(base+path)
    self.assertEqual(e.exception.code,404);e.exception.close()
   req=Request(base+'/api/sessions',data=b'{}',headers={'Content-Type':'application/json','Origin':'https://evil.example'})
   with self.assertRaises(HTTPError) as e:urlopen(req)
   self.assertEqual(e.exception.code,403);e.exception.close()
   req=Request(base+'/api/actions',data=b'{',headers={'Content-Type':'application/json'})
   with self.assertRaises(HTTPError) as e:urlopen(req)
   self.assertEqual(e.exception.code,400);e.exception.close()
   req=Request(base+'/api/state',headers={'X-Session-ID':'x'*300})
   with self.assertRaises(HTTPError) as e:urlopen(req)
   self.assertEqual(e.exception.code,400);e.exception.close()
  finally:server.shutdown();server.server_close();thread.join()
 def test_approved_answer_reaches_only_the_same_session(self):
  aid=self.store.start(self.sid,'S01')
  self.store.inspect(self.sid,aid,'handbook-v1')
  self.store.record(self.sid,aid,'ask-0001','ask_expert','Which revision can accept P-100B?',['handbook-v1'])
  self.store.review(self.sid,aid,'P-100B fits revision R2 when certificate C-B is present.','approve')
  with self.assertRaises(ValueError): self.store.review(self.sid,aid,'A second answer.','approve')
  card='\n'.join(self.store.inspect(self.sid,self.store.start(self.sid,'S02'),'approved-guidance')['content'])
  self.assertIn('revision R2',card)
  self.assertNotIn('expected_action',json.dumps(self.store.state(self.sid)))
  other=self.store.create()
  hidden='\n'.join(self.store.inspect(other,self.store.start(other,'S02'),'approved-guidance')['content'])
  self.assertNotIn('revision R2',hidden)
 def test_rejected_answer_is_not_published(self):
  aid=self.store.start(self.sid,'S01')
  self.store.inspect(self.sid,aid,'case-facts')
  self.store.record(self.sid,aid,'ask-0002','ask_expert','What is the rule?',['case-facts'])
  self.store.review(self.sid,aid,'Do not publish this.','reject')
  card='\n'.join(self.store.inspect(self.sid,self.store.start(self.sid,'S02'),'approved-guidance')['content'])
  self.assertNotIn('Do not publish this.',card)
  with self.assertRaises(ValueError): self.store.review(self.sid,self.store.start(self.sid,'C01'),'No question yet.','approve')
 def reply(self, payload, category='knowledge', question='Which condition is missing?'):
  encoded=json.dumps(payload)
  self.assertNotIn('accept_if', encoded)
  self.assertNotIn('Expert-only', encoded)
  user=json.loads(payload['messages'][1]['content'])
  body={'category':category,'missing_distinction':'The handbook does not cover this case.','evidence_refs':[item['id'] for item in user['evidence']],'expert_question':question,'uncertainties':['The hidden rule is not in the evidence.']}
  return {'model':'test-model','usage':{'prompt_tokens':120,'completion_tokens':40},'choices':[{'finish_reason':'stop','message':{'content':json.dumps(body)}}]}
 def test_control_cases_cover_decision_evidence_and_permission(self):
  checks={'C01':'accept','C02':'request_evidence','C03':'report_permission_issue','C04':'escalate'}
  for cid, action in checks.items():
   aid=self.store.start(self.sid,cid)
   self.record(self.sid,aid,'event-'+cid,action,'Control-case check')
   result=self.store.state(self.sid)['attempts'][-1]['result']
   self.assertTrue(result['correct_action'],cid)
   self.assertTrue(result['safe_handling'],cid)
   self.assertEqual(result['independent_completion'],cid=='C01')
 def test_diagnosis_asks_from_opened_evidence_only(self):
  aid=self.store.start(self.sid,'S01')
  with self.assertRaises(ValueError): self.store.diagnose(self.sid,aid,transport=lambda payload: self.reply(payload))
  self.store.inspect(self.sid,aid,'handbook-v1')
  found=self.store.diagnose(self.sid,aid,transport=lambda payload: self.reply(payload))
  self.assertEqual(found['category'],'knowledge')
  self.assertEqual(found['suggested_action'],'ask_expert')
  saved=self.store.state(self.sid)['attempts'][0]
  self.assertEqual(saved['actions'],[])
  self.assertEqual(saved['diagnosis']['expert_question'], 'Which condition is missing?')
  self.assertEqual(saved['diagnosis']['evidence_refs'], ['handbook-v1'])
  self.assertEqual(saved['diagnosis']['suggested_action'], 'ask_expert')
  self.assertLess(found['spent_usd'],5)
 def test_diagnosis_distinguishes_missing_evidence_and_permission(self):
  for cid, category, action in (('C02','missing_case_data','request_evidence'),('C03','permission','report_permission_issue')):
   aid=self.store.start(self.sid,cid)
   self.store.inspect(self.sid,aid,'case-facts')
   found=self.store.diagnose(self.sid,aid,transport=lambda payload, category=category: self.reply(payload,category,'What is missing?'))
   self.assertEqual(found['suggested_action'],action)
 def test_failed_diagnosis_leaves_the_attempt_unchanged(self):
  aid=self.store.start(self.sid,'S01')
  self.store.inspect(self.sid,aid,'handbook-v1')
  def fail(payload):
   raise ModelError('Meta did not respond in time. The attempt was not changed. Retry the diagnosis.')
  with self.assertRaises(ModelError): self.store.diagnose(self.sid,aid,transport=fail)
  self.assertIsNone(self.store.state(self.sid)['attempts'][0]['diagnosis'])
  self.assertEqual(self.store.spent(),0)
 def test_budget_stops_before_another_call(self):
  aid=self.store.start(self.sid,'S01')
  self.store.inspect(self.sid,aid,'handbook-v1')
  with self.store.db() as db:
   db.execute('INSERT INTO api_spend(created,model,cost_usd) VALUES (?,?,?)',('2026-10-27T00:00:00Z','test',5))
  calls=[]
  with self.assertRaises(ModelError): self.store.diagnose(self.sid,aid,transport=lambda payload: calls.append(payload))
  self.assertEqual(calls,[])
 def model_reply(self, payload, body):
  self.assertNotIn('accept_if', json.dumps(payload))
  self.assertEqual(payload['model'], 'meta-models/muse-spark-open-1026')
  return {'model':'meta-models/muse-spark-open-1026','usage':{'prompt_tokens':20,'completion_tokens':20},'choices':[{'finish_reason':'stop','message':{'content':json.dumps(body)}}]}
 def test_draft_quotes_the_expert_and_does_not_publish(self):
  aid=self.store.start(self.sid,'S01')
  self.store.inspect(self.sid,aid,'handbook-v1')
  self.store.record(self.sid,aid,'ask-draft','ask_expert','Which revision is covered?',['handbook-v1'])
  answer='P-100B is allowed only on R2 with certificate C-B.'
  found=self.store.draft_card(self.sid,aid,answer,transport=lambda payload: self.model_reply(payload,{'card':'Apply only the stated exception.','quote':'only on R2 with certificate C-B.','abstain_when':'the certificate is different'}))
  self.assertIn('only on R2 with certificate C-B.', found['card'])
  self.assertEqual(self.store.state(self.sid)['summary']['approved_guidance'],0)
  with self.assertRaises(ModelError):
   self.store.draft_card(self.sid,aid,answer,transport=lambda payload: self.model_reply(payload,{'card':'Invented.','quote':'a rule the expert did not say','abstain_when':''}))
 def test_suggestion_does_not_save_the_decision(self):
  aid=self.store.start(self.sid,'S02')
  self.store.inspect(self.sid,aid,'handbook-v1')
  found=self.store.suggest(self.sid,aid,transport=lambda payload: self.model_reply(payload,{'action':'ask_expert','reason':'No approved card covers this order.','evidence_refs':['handbook-v1']}))
  self.assertEqual(found['action'],'ask_expert')
  self.assertEqual(self.store.state(self.sid)['attempts'][-1]['actions'],[])
  from app.model import recommend_messages
  instruction=recommend_messages({'case_id':'S05'},[])[0]['content']
  self.assertIn('outside its exception', instruction)
  self.assertIn('action is reject', instruction)
 def test_an_edit_is_not_published_until_approved_again(self):
  aid=self.store.start(self.sid,'S01')
  self.store.inspect(self.sid,aid,'handbook-v1')
  self.store.record(self.sid,aid,'ask-edit','ask_expert','Which revision is covered?',['handbook-v1'])
  answer='Only revision R2 with certificate C-B is covered.'
  self.store.draft_card(self.sid,aid,answer,transport=lambda payload: self.model_reply(payload,{'card':'Only the stated revision.','quote':'Only revision R2 with certificate C-B is covered.','abstain_when':'other certificates'}))
  first=self.store.review(self.sid,aid,'A different condition.','approve')
  self.assertFalse(first['published'])
  self.assertTrue(first['needs_review'])
  self.assertEqual(self.store.state(self.sid)['summary']['approved_guidance'],0)
  second=self.store.review(self.sid,aid,'A different condition.','approve')
  self.assertTrue(second['published'])
 def test_not_knowing_publishes_no_card(self):
  aid=self.store.start(self.sid,'S01')
  self.store.inspect(self.sid,aid,'case-facts')
  self.store.record(self.sid,aid,'ask-unknown','ask_expert','What is the rule?',['case-facts'])
  result=self.store.review(self.sid,aid,"I don't know",'abstain')
  self.assertTrue(result['abstained'])
  self.assertFalse(result['published'])
  card='\n'.join(self.store.inspect(self.sid,self.store.start(self.sid,'S02'),'approved-guidance')['content'])
  self.assertIn('No expert-approved',card)
 def test_api_key_stays_off_the_client_payload(self):
  secret='sk-test-secret-value-should-not-leak'
  names=('MODEL_PROVIDER','BASETEN_API_KEY','MODEL_API_KEY')
  saved={name: os.environ.get(name) for name in names}
  os.environ['MODEL_PROVIDER']='baseten'
  os.environ['BASETEN_API_KEY']=secret
  try:
   payload=self.store.state(self.sid)
   encoded=json.dumps(payload)
   self.assertNotIn('key', payload)
   self.assertNotIn(secret, encoded)
   self.assertNotIn('BASETEN_API_KEY', encoded)
   self.assertEqual(payload['model_status'], 'ready')
   self.assertEqual(payload['setup_message'], '')
  finally:
   for name, value in saved.items():
    if value is None: os.environ.pop(name, None)
    else: os.environ[name]=value
 def test_a_later_card_does_not_change_an_earlier_attempt(self):
  early=self.store.start(self.sid,'S02')
  aid=self.store.start(self.sid,'S01')
  self.store.inspect(self.sid,aid,'handbook-v1')
  self.store.record(self.sid,aid,'ask-freeze','ask_expert','Which revision?',['handbook-v1'])
  self.store.review(self.sid,aid,'Only R2 with C-B.','approve')
  before='\n'.join(self.store.inspect(self.sid,early,'approved-guidance')['content'])
  after='\n'.join(self.store.inspect(self.sid,self.store.start(self.sid,'S03'),'approved-guidance')['content'])
  self.assertIn('No expert-approved',before)
  self.assertIn('Only R2 with C-B.',after)
 def approve_card(self, text):
  aid=self.store.start(self.sid,'S01')
  self.store.inspect(self.sid,aid,'handbook-v1')
  self.store.record(self.sid,aid,'ask-attack','ask_expert','Which substitution is allowed?',['handbook-v1'])
  self.store.review(self.sid,aid,text,'approve')
  return aid
 def orders(self):
  base={'supplier':'Northline','ordered_part':'P-100','offered_part':'P-100B','quantity':4}
  return [
   {'condition':'wrong_certificate','facts':{**base,'machine_revision':'R2','certificate':'C-A'},'note':'Certificate C-A is outside the named certificate.'},
   {'condition':'missing_certificate','facts':{**base,'machine_revision':'R2','certificate':None},'note':'The certificate is missing.'},
   {'condition':'lookalike_revision','facts':{**base,'machine_revision':'R1','certificate':'C-B'},'note':'Revision R1 is only a lookalike.'},
  ]
 def attack_transport(self, actions):
  def transport(payload):
   encoded=json.dumps(payload)
   self.assertNotIn('accept_if', encoded)
   self.assertNotIn('R-SUB', encoded)
   self.assertNotIn('independently_completable', encoded)
   self.assertNotIn('may replace', encoded)
   self.assertNotIn('graded_action', encoded)
   user=json.loads(payload['messages'][1]['content'])
   if 'used_orders' in user:
    self.assertEqual(set(user), {'card','used_orders'})
    return self.model_reply(payload, {'attacks': self.orders()})
   facts=user['case']['facts']
   if facts['certificate'] is None: action='request_evidence'
   elif facts['machine_revision']=='R1': action=actions.get('lookalike','reject')
   else: action=actions.get('wrong','reject')
   return self.model_reply(payload, {'action':action,'reason':'Applied only the approved card.','evidence_refs':['approved-guidance']})
  return transport
 def test_generated_orders_use_the_fixture_grader(self):
  from app.grade import grade
  for case in self.store.cases.values():
   self.assertEqual(grade(case), self.store.expected[case['case_id']]['expected_action'])
 def test_attack_requires_an_approved_substitution_card(self):
  calls=[]
  with self.assertRaises(ValueError): self.store.attack(self.sid, transport=lambda payload: calls.append(payload))
  self.assertEqual(calls,[])
 def test_a_card_that_holds_does_not_open_a_new_draft(self):
  self.approve_card('Only revision R2 with certificate C-B is covered.')
  found=self.store.attack(self.sid, transport=self.attack_transport({'wrong':'reject','lookalike':'reject'}))
  self.assertEqual([item['verdict'] for item in found['attacks']], ['held','held','held'])
  self.assertFalse(found['draft_created'])
  state=self.store.state(self.sid)
  self.assertEqual(state['summary']['approved_guidance'],1)
  self.assertEqual(state['summary']['attacks_held'],3)
  self.assertFalse(state['summary']['pending_attack'])
  encoded=json.dumps(state)
  for forbidden in ('expected_action','accept_if','independently_completable'):
   self.assertNotIn(forbidden, encoded)
 def test_a_failed_attack_keeps_the_old_card_until_a_tighter_one_is_approved(self):
  aid=self.approve_card('VAGUE-CARD accept every Northline alternative.')
  early=self.store.start(self.sid,'S02')
  found=self.store.attack(self.sid, transport=self.attack_transport({'wrong':'accept','lookalike':'reject'}))
  self.assertTrue(found['draft_created'])
  self.assertIn('wrong', [item['verdict'] for item in found['attacks']])
  state=self.store.state(self.sid)
  self.assertEqual(state['summary']['approved_guidance'],1)
  self.assertTrue(state['summary']['pending_attack'])
  gap=next(gap for item in state['attempts'] if item['id']==aid for gap in item['gaps'] if gap['status']=='open')
  self.assertTrue(gap['question'].startswith('Attack:'))
  visible='\n'.join(self.store.inspect(self.sid, early, 'approved-guidance')['content'])
  self.assertIn('VAGUE-CARD', visible)
  self.assertNotIn('not approved guidance', visible)
  calls=[]
  with self.assertRaises(ValueError): self.store.attack(self.sid, transport=lambda payload: calls.append(payload))
  self.assertEqual(calls,[])
  during=self.store.start(self.sid,'S03')
  self.assertIn('VAGUE-CARD', '\n'.join(self.store.inspect(self.sid, during, 'approved-guidance')['content']))
  published=self.store.review(self.sid, aid, 'TIGHTER-CARD only R2 with C-B.', 'approve')
  self.assertTrue(published['published'])
  self.assertTrue(published['superseded_previous'])
  later='\n'.join(self.store.inspect(self.sid, self.store.start(self.sid,'S04'), 'approved-guidance')['content'])
  early_card='\n'.join(self.store.inspect(self.sid, early, 'approved-guidance')['content'])
  self.assertIn('TIGHTER-CARD', later)
  self.assertNotIn('VAGUE-CARD', later)
  self.assertIn('VAGUE-CARD', early_card)
  self.assertNotIn('TIGHTER-CARD', early_card)
  self.assertEqual(self.store.state(self.sid)['summary']['approved_guidance'],1)
  self.assertFalse(self.store.state(self.sid)['summary']['pending_attack'])
 def test_a_failed_attack_call_saves_nothing(self):
  self.approve_card('Only R2 with C-B.')
  def fail(payload):
   raise ModelError('down')
  with self.assertRaises(ModelError): self.store.attack(self.sid, transport=fail)
  self.assertEqual(self.store.state(self.sid)['attacks'], [])
 def test_an_attack_that_states_an_outcome_is_not_saved(self):
  self.approve_card('Only R2 with C-B.')
  def transport(payload):
   user=json.loads(payload['messages'][1]['content'])
   if 'used_orders' in user:
    attacks=self.orders(); attacks[0]['action']='reject'
    return self.model_reply(payload, {'attacks': attacks})
   return self.model_reply(payload, {'action':'reject','reason':'Applied only the approved card.','evidence_refs':['approved-guidance']})
  with self.assertRaises(ModelError): self.store.attack(self.sid, transport=transport)
  self.assertEqual(self.store.state(self.sid)['attacks'], [])
if __name__=='__main__':unittest.main()
