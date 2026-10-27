import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
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
   with urlopen(base+'/health') as response: self.assertEqual(json.load(response)['status'],'ok')
   for path in ['/03-scenarios/expert-only/rulebook.json','/../.env','/app/server.py','/api/state']:
    with self.assertRaises(HTTPError) as e:urlopen(base+path)
    self.assertEqual(e.exception.code,404);e.exception.close()
   req=Request(base+'/api/sessions',data=b'{}',headers={'Content-Type':'application/json','Origin':'https://evil.example'})
   with self.assertRaises(HTTPError) as e:urlopen(req)
   self.assertEqual(e.exception.code,403);e.exception.close()
   req=Request(base+'/api/actions',data=b'{',headers={'Content-Type':'application/json'})
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
if __name__=='__main__':unittest.main()
