"""Meta diagnosis calls. The key stays in memory and is never returned to the browser."""
from __future__ import annotations

import json
import logging
import os
import ssl
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

log = logging.getLogger('missingmonday.model')

BUDGET_USD = 5.0
INPUT_USD_PER_MILLION = 1.25
CACHED_USD_PER_MILLION = 0.15
OUTPUT_USD_PER_MILLION = 4.25
CATEGORIES = ('knowledge', 'permission', 'tool_failure', 'missing_case_data', 'ambiguous_task', 'unknown')
ACTION_FOR = {
    'knowledge': 'ask_expert',
    'unknown': 'ask_expert',
    'missing_case_data': 'request_evidence',
    'permission': 'report_permission_issue',
    'tool_failure': 'escalate',
    'ambiguous_task': 'escalate',
}
ENV_PATHS = (
    Path(__file__).resolve().parents[1] / '.env',
    Path(__file__).resolve().parents[2] / '.env',
)

class ModelError(RuntimeError):
    pass

def _parse_env(path):
    values = {}
    if not path.is_file():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values

def _value(found, name):
    return os.environ.get(name, '').strip() or found.get(name, '')

_ENV_NAMES = ('MODEL_PROVIDER', 'MODEL_API_KEY', 'META_MODEL', 'BASETEN_API_KEY', 'BASETEN_MODEL')
_RUNTIME_CACHE: dict = {'token': None, 'value': None}

def _load_runtime():
    found = {}
    for path in ENV_PATHS:
        found.update({key: value for key, value in _parse_env(path).items() if value})
    provider = _value(found, 'MODEL_PROVIDER').lower() or 'baseten'
    if provider == 'meta':
        key = _value(found, 'MODEL_API_KEY')
        missing = '' if key else 'MODEL_API_KEY is not set. Add it to .env. No call was made.'
        return {'provider': 'meta', 'label': 'Meta', 'key': key, 'model': _value(found, 'META_MODEL') or 'muse-spark-1.3', 'url': 'https://api.meta.ai/v1/chat/completions', 'missing': missing}
    key = _value(found, 'BASETEN_API_KEY')
    missing = '' if key else 'BASETEN_API_KEY is not set. Add it to .env. No call was made.'
    return {'provider': 'baseten', 'label': 'Baseten', 'key': key, 'model': _value(found, 'BASETEN_MODEL') or 'meta-models/muse-spark-open-1026', 'url': 'https://inference.baseten.co/v1/chat/completions', 'missing': missing}

def _runtime_token():
    stamps = []
    for path in ENV_PATHS:
        try:
            stamps.append(path.stat().st_mtime_ns if path.is_file() else 0)
        except OSError:
            stamps.append(0)
    return (tuple(stamps), tuple(os.environ.get(name, '') for name in _ENV_NAMES))

def runtime():
    token = _runtime_token()
    if _RUNTIME_CACHE['token'] != token:
        _RUNTIME_CACHE['token'] = token
        _RUNTIME_CACHE['value'] = _load_runtime()
    return dict(_RUNTIME_CACHE['value'])

def call_cost(usage):
    if not isinstance(usage, dict):
        return 0.02
    incoming = usage.get('input_tokens', usage.get('prompt_tokens', 0)) or 0
    outgoing = usage.get('output_tokens', usage.get('completion_tokens', 0)) or 0
    details = usage.get('input_tokens_details') or usage.get('prompt_tokens_details') or {}
    cached = details.get('cached_tokens', 0) if isinstance(details, dict) else 0
    fresh = max(0, incoming - cached)
    return (fresh * INPUT_USD_PER_MILLION + cached * CACHED_USD_PER_MILLION + outgoing * OUTPUT_USD_PER_MILLION) / 1_000_000

def ssl_context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass
    for path in ('/etc/ssl/cert.pem', '/private/etc/ssl/cert.pem'):
        if os.path.isfile(path):
            return ssl.create_default_context(cafile=path)
    return ssl.create_default_context()

def _post(payload, conf):
    request = Request(
        conf['url'],
        data=json.dumps(payload).encode(),
        headers={'Authorization': f'Bearer {conf["key"]}', 'Content-Type': 'application/json'},
        method='POST',
    )
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=90, context=ssl_context()) as response:
            body = json.load(response)
    except HTTPError as error:
        log.warning('%s returned HTTP %s', conf['label'], error.code)
        raise ModelError(f'{conf["label"]} returned HTTP {error.code}. The attempt was not changed. Retry the diagnosis.') from None
    except (URLError, TimeoutError, json.JSONDecodeError):
        log.warning('%s did not respond', conf['label'])
        raise ModelError(f'{conf["label"]} did not respond. The attempt was not changed. Retry the diagnosis.') from None
    usage = body.get('usage') if isinstance(body, dict) else {}
    if not isinstance(usage, dict):
        usage = {}
    log.info(
        '%s responded in %dms in=%s out=%s',
        conf['label'],
        int((time.perf_counter() - started) * 1000),
        usage.get('input_tokens', usage.get('prompt_tokens')),
        usage.get('output_tokens', usage.get('completion_tokens')),
    )
    return body

def _read_choice(raw):
    choice = raw['choices'][0]
    content = choice['message']['content']
    if isinstance(content, list):
        content = ''.join(part.get('text', '') for part in content if isinstance(part, dict))
    return content if isinstance(content, str) else '', choice.get('finish_reason')

def complete(messages, transport=None):
    conf = runtime()
    # Muse Spark Open spends the completion budget on reasoning before it writes the answer.
    payload = {'model': conf['model'], 'messages': messages}
    if conf['provider'] == 'meta':
        payload['reasoning_effort'] = 'low'
    limits = [2500, 6000] if conf['provider'] == 'baseten' and transport is None else [700 if conf['provider'] == 'meta' else 2500]
    if not transport and not conf['key']:
        raise ModelError(conf['missing'])
    cost = 0
    content, finish, raw = '', None, {}
    for limit in limits:
        payload['max_completion_tokens'] = limit
        raw = transport(payload) if transport else _post(payload, conf)
        cost += call_cost(raw.get('usage') or {})
        try:
            content, finish = _read_choice(raw)
        except (KeyError, IndexError, TypeError):
            raise ModelError(f'{conf["label"]} returned an incomplete diagnosis. The attempt was not changed. Retry the diagnosis.') from None
        if content.strip() or finish != 'length' or transport:
            break
    if not content.strip():
        if finish == 'length':
            raise ModelError(f'{conf["label"]} used the token budget on reasoning before writing an answer. The attempt was not changed.')
        raise ModelError(f'{conf["label"]} returned an incomplete diagnosis. The attempt was not changed. Retry the diagnosis.')
    return {'content': content, 'model': raw.get('model', conf['model']), 'usage': raw.get('usage') or {}, 'cost': cost}

def card_messages(question, answer):
    system = (
        'Turn one expert answer into a short guidance card. Use only that answer. '
        'Do not add a condition the expert did not state. quote must be copied exactly from the answer. '
        'Return one JSON object with keys card, quote, abstain_when. card is one or two sentences. abstain_when says when not to apply it.'
    )
    return [{'role': 'system', 'content': system}, {'role': 'user', 'content': json.dumps({'question': question, 'expert_answer': answer}, ensure_ascii=False)}]

ATTACK_CONDITIONS = ('wrong_certificate', 'missing_certificate', 'lookalike_revision')
ATTACK_FIELDS = ('supplier', 'ordered_part', 'offered_part', 'machine_revision', 'certificate', 'quantity')


def attack_messages(card, used_orders):
    system = (
        'Propose synthetic purchasing orders that could make a successor misapply one approved card. '
        'Use only the card and the orders already seen. Do not state a correct action, a hidden company rule, or an expected outcome. '
        'Return one JSON object with key attacks. attacks has two or three objects. '
        'Each object has keys condition, facts, note. '
        'condition is wrong_certificate, missing_certificate, or lookalike_revision, and each condition appears at most once. '
        'facts has supplier, ordered_part, offered_part, machine_revision, certificate, quantity. '
        'certificate is a string or null. machine_revision is a string. quantity is an integer from 1 to 999. '
        'For wrong_certificate, certificate is a non-empty string. '
        'For missing_certificate, certificate is null. '
        'For lookalike_revision, certificate is a non-empty string and machine_revision differs from the revision the card allows. '
        'note is one sentence naming the condition under test. Do not include an action.'
    )
    payload = {'card': card, 'used_orders': used_orders}
    return [{'role': 'system', 'content': system}, {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)}]


def _plain(value, label):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 80:
        raise ModelError(f'The attack returned an unusable {label}. Nothing was saved.')
    return value.strip()


def parse_attacks(content):
    data = _object(content)
    attacks = data.get('attacks')
    if not isinstance(attacks, list) or not 2 <= len(attacks) <= 3:
        raise ModelError('The attack did not return two or three orders. Nothing was saved.')
    found = []
    seen = set()
    for item in attacks:
        if not isinstance(item, dict) or any(key in item for key in ('action', 'expected', 'expected_action', 'graded_action')):
            raise ModelError('The attack included an outcome. Nothing was saved.')
        condition, facts, note = item.get('condition'), item.get('facts'), item.get('note')
        if condition not in ATTACK_CONDITIONS or condition in seen:
            raise ModelError('The attack used an unknown or repeated condition. Nothing was saved.')
        seen.add(condition)
        if not isinstance(facts, dict) or set(facts) != set(ATTACK_FIELDS):
            raise ModelError('The attack returned order fields that cannot be graded. Nothing was saved.')
        if not isinstance(note, str) or not note.strip() or len(note.strip()) > 300:
            raise ModelError('The attack did not name the condition under test. Nothing was saved.')
        quantity = facts.get('quantity')
        if isinstance(quantity, str) and quantity.isdigit():
            quantity = int(quantity)
        if isinstance(quantity, bool) or not isinstance(quantity, int) or not 1 <= quantity <= 999:
            raise ModelError('The attack returned an unusable quantity. Nothing was saved.')
        certificate = facts.get('certificate')
        if condition == 'missing_certificate':
            if certificate is not None:
                raise ModelError('The missing-certificate attack included a certificate. Nothing was saved.')
            certificate = None
        else:
            certificate = _plain(certificate, 'certificate')
        cleaned = {
            'supplier': _plain(facts.get('supplier'), 'supplier'),
            'ordered_part': _plain(facts.get('ordered_part'), 'ordered part'),
            'offered_part': _plain(facts.get('offered_part'), 'offered part'),
            'machine_revision': _plain(facts.get('machine_revision'), 'machine revision'),
            'certificate': certificate,
            'quantity': quantity,
        }
        found.append({'condition': condition, 'facts': cleaned, 'note': note.strip()})
    return found


def recommend_messages(case, documents):
    system = (
        'Suggest one next step for a synthetic purchasing case. Use only the evidence in the user message. '
        'Do not invent a company rule. If an approved card says these facts are outside its exception, action is reject. '
        'Use ask_expert only when no approved card discusses this supplier and part. '
        'action is one of accept, reject, request_evidence, escalate, report_permission_issue, ask_expert. '
        'Return one JSON object with keys action, reason, evidence_refs. evidence_refs copies ids from the evidence list.'
    )
    return [{'role': 'system', 'content': system}, {'role': 'user', 'content': json.dumps({'case': case, 'evidence': documents}, ensure_ascii=False)}]

def _object(content):
    text = content.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find('{'), text.rfind('}')
        try:
            data = json.loads(text[start:end + 1]) if start != -1 and end > start else None
        except json.JSONDecodeError:
            data = None
    if not isinstance(data, dict):
        raise ModelError('The model did not return the requested fields. Nothing was published. Retry.')
    return data

def parse_card(content, answer):
    data = _object(content)
    card, quote = data.get('card'), data.get('quote')
    abstain = data.get('abstain_when') or ''
    if not isinstance(card, str) or not card.strip() or not isinstance(quote, str) or quote not in answer:
        raise ModelError('The draft did not quote the expert answer. Nothing was published.')
    if not isinstance(abstain, str):
        abstain = ''
    text = f'{card.strip()} Quote: "{quote.strip()}"'
    if abstain.strip():
        text += f' Do not use this card when: {abstain.strip()}'
    if len(text) > 2000:
        raise ModelError('The draft was too long. Nothing was published.')
    return text

def parse_recommendation(content, allowed_ids, allowed_actions):
    data = _object(content)
    action, reason, refs = data.get('action'), data.get('reason'), data.get('evidence_refs')
    permitted = set(allowed_actions) | {'ask_expert'}
    if action not in permitted or not isinstance(reason, str) or not reason.strip():
        raise ModelError('The suggestion was not a permitted next step. Nothing was saved.')
    if not isinstance(refs, list) or not refs or any(not isinstance(ref, str) or ref not in allowed_ids for ref in refs):
        raise ModelError('The suggestion cited evidence that was not opened. Nothing was saved.')
    return {'action': action, 'reason': reason.strip()[:2000], 'evidence_refs': sorted(set(refs))}

def diagnosis_messages(case, documents):
    system = (
        'Diagnose one stalled synthetic purchasing case. Use only the evidence in the user message. '
        'Do not invent a company rule or the correct final action. '
        'category is knowledge when the handbook has no rule for this exception, missing_case_data when a required fact is absent, '
        'permission when access is missing, otherwise tool_failure, ambiguous_task, or unknown. '
        'Return one JSON object and nothing else, with keys category, missing_distinction, evidence_refs, expert_question, uncertainties. '
        'evidence_refs copies ids from the evidence list. expert_question is one short question. uncertainties is a short array.'
    )
    user = json.dumps({'case': case, 'evidence': documents}, ensure_ascii=False)
    return [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]

def parse_diagnosis(content, allowed_ids, allowed_actions):
    data = _object(content)
    if data.get('category') not in CATEGORIES:
        raise ModelError('Meta returned an unknown blockage category. The attempt was not changed.')
    refs = data.get('evidence_refs')
    if not isinstance(refs, list) or not refs or any(not isinstance(ref, str) or ref not in allowed_ids for ref in refs):
        raise ModelError('Meta cited evidence that was not opened. The attempt was not changed.')
    question = data.get('expert_question')
    distinction = data.get('missing_distinction')
    if not isinstance(question, str) or not question.strip() or len(question.strip()) > 2000:
        raise ModelError('Meta did not return one usable question. The attempt was not changed.')
    if not isinstance(distinction, str) or not distinction.strip() or len(distinction.strip()) > 500:
        raise ModelError('Meta did not name the missing distinction. The attempt was not changed.')
    uncertainties = data.get('uncertainties')
    if not isinstance(uncertainties, list):
        uncertainties = []
    action = ACTION_FOR[data['category']]
    if action not in allowed_actions and action != 'ask_expert':
        action = 'escalate' if 'escalate' in allowed_actions else 'ask_expert'
    return {
        'category': data['category'],
        'missing_distinction': distinction.strip(),
        'evidence_refs': sorted(set(refs)),
        'expert_question': question.strip(),
        'uncertainties': [str(item)[:300] for item in uncertainties[:5] if str(item).strip()],
        'suggested_action': action,
    }
