"""Meta diagnosis calls. The key stays in memory and is never returned to the browser."""
import json
import os
import ssl
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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

def runtime():
    found = {}
    for path in ENV_PATHS:
        found.update({key: value for key, value in _parse_env(path).items() if value})
    provider = _value(found, 'MODEL_PROVIDER').lower() or 'baseten'
    if provider == 'meta':
        return {'provider': 'meta', 'label': 'Meta', 'key': _value(found, 'MODEL_API_KEY'), 'model': _value(found, 'META_MODEL') or 'muse-spark-1.3', 'url': 'https://api.meta.ai/v1/chat/completions', 'missing': 'MODEL_API_KEY is not set. Add it to .env. No call was made.'}
    return {'provider': 'baseten', 'label': 'Baseten', 'key': _value(found, 'BASETEN_API_KEY'), 'model': _value(found, 'BASETEN_MODEL') or 'meta-models/muse-spark-open-1026', 'url': 'https://inference.baseten.co/v1/chat/completions', 'missing': 'BASETEN_API_KEY is not set. Add it to .env. No call was made.'}

def configured():
    return bool(runtime()['key'])

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
    try:
        with urlopen(request, timeout=90, context=ssl_context()) as response:
            return json.load(response)
    except HTTPError as error:
        raise ModelError(f'{conf["label"]} returned HTTP {error.code}. The attempt was not changed. Retry the diagnosis.') from None
    except (URLError, TimeoutError, json.JSONDecodeError):
        raise ModelError(f'{conf["label"]} did not respond. The attempt was not changed. Retry the diagnosis.') from None

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
