const $ = (id) => document.getElementById(id);

function stored(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}

function remember(key, value) {
  try { localStorage.setItem(key, value); return true; } catch { return false; }
}

let sid = stored('mm-session');
let state;
let active;
let selectedId = stored('mm-active');
let pending = null;
let working = false;

const draftsKey = () => `mm-draft:${sid}:${active?.id}`;

function draft() {
  try { return JSON.parse(stored(draftsKey()) || '{}'); } catch { return {}; }
}

function saveDraft() {
  if (!active || active.result) return;
  const data = {
    reason: $('reason').value,
    action: $('action').value,
    category: $('category').value,
    refs: [...$('citations').querySelectorAll('input:checked')].map((box) => box.value),
    pending,
    expert: $('expert-answer').value,
  };
  const saved = remember(draftsKey(), JSON.stringify(data));
  $('draft-status').textContent = saved
    ? 'Draft saved on this device.'
    : 'Draft could not be saved on this device. Keep this tab open.';
}

function categoryVisibility() {
  const show = ['ask_expert', 'escalate'].includes($('action').value);
  $('category').hidden = !show;
  $('category-label').hidden = !show;
}

function error(err) {
  const node = $('error');
  node.textContent = err.message;
  node.hidden = false;
  node.focus();
}

function toast(message) {
  const host = $('toasts');
  host.replaceChildren();
  const node = document.createElement('p');
  node.className = 'toast';
  node.textContent = message;
  host.append(node);
  window.setTimeout(() => { if (node.isConnected) node.remove(); }, 3200);
}

async function api(path, body) {
  const response = await fetch(path, {
    method: body ? 'POST' : 'GET',
    headers: {'Content-Type': 'application/json', ...(sid ? {'X-Session-ID': sid} : {})},
    ...(body ? {body: JSON.stringify(body)} : {}),
  });
  const data = await response.json();
  if (!response.ok) {
    const err = new Error(data.error || 'Request failed');
    err.status = response.status;
    throw err;
  }
  return data;
}

function text(tag, value) {
  const node = document.createElement(tag);
  node.textContent = value;
  return node;
}

function lock(disabled) {
  document.querySelectorAll('button, select, textarea, input').forEach((node) => {
    if (!disabled && node.dataset.keepDisabled === 'true') return;
    node.disabled = disabled;
  });
}

async function refresh() {
  state = await api('/api/state');
  render();
}

async function busy(button, fn) {
  if (working) return;
  working = true;
  document.body.classList.add('is-working');
  document.body.setAttribute('aria-busy', 'true');
  lock(true);
  $('error').hidden = true;
  $('error').textContent = '';
  const note = $('model-note');
  const previous = note ? note.textContent : '';
  const slow = button && ['diagnose', 'suggest', 'draft', 'attack'].includes(button.id);
  const providerLabel = state?.provider === 'meta' ? 'Meta' : 'Baseten';
  const workingNote = `${providerLabel} is working. This can take a few seconds.`;
  if (slow && note) note.textContent = workingNote;
  try {
    await fn();
  } catch (err) {
    error(err);
    if (note) note.textContent = previous;
  } finally {
    working = false;
    document.body.classList.remove('is-working');
    document.body.removeAttribute('aria-busy');
    if (slow && note && note.textContent === workingNote) note.textContent = previous;
    lock(false);
  }
}

function clean() {
  for (const input of $('citations').querySelectorAll('input')) input.checked = false;
  pending = null;
  $('reason').value = '';
  $('document').hidden = true;
}

function fillCases(selected) {
  const groups = [];
  for (const item of state.cases) {
    let group = groups.find((entry) => entry.family === item.family);
    if (!group) {
      group = {family: item.family, cases: []};
      groups.push(group);
    }
    group.cases.push(item);
  }
  $('case').replaceChildren(...groups.map((group) => {
    const label = document.createElement('optgroup');
    label.label = state.family_labels[group.family] || group.family;
    label.append(...group.cases.map((item) => {
      const option = text('option', item.label);
      option.value = item.id;
      return option;
    }));
    return label;
  }));
  if (selected) $('case').value = selected;
}

function stageFor(attempt) {
  if (state?.summary?.pending_attack) return 'attack';
  if (!attempt) return 'rehearse';
  if (attempt.case.split === 'transfer' || attempt.case.split === 'boundary') return 'retest';
  if (attempt.gaps.some((gap) => gap.status === 'open' && (gap.category === 'knowledge' || gap.category === 'unknown'))) return 'capture';
  return 'rehearse';
}

function markStages(stage) {
  const done = {
    rehearse: state.summary.attempts > 0,
    capture: state.summary.approved_guidance > 0,
    retest: state.attempts.some((item) => (item.case.split === 'transfer' || item.case.split === 'boundary') && item.result),
    attack: state.attacks.length > 0 && !state.summary.pending_attack,
  };
  document.body.dataset.stage = stage;
  for (const item of $('stages').querySelectorAll('[data-stage]')) {
    const name = item.dataset.stage;
    const current = name === stage;
    item.classList.toggle('current', current);
    item.classList.toggle('done', Boolean(done[name]) && !current);
    if (current) item.setAttribute('aria-current', 'step');
    else item.removeAttribute('aria-current');
  }
}

function paintSpend() {
  const spent = Number(state.spend.spent_usd);
  const budget = Number(state.spend.budget_usd) || 0;
  const pct = budget ? Math.min(100, Math.max(0, (spent / budget) * 100)) : 0;
  const bucket = Math.round(pct / 5) * 5;
  $('spend-fill').className = `spend-fill p${bucket}${pct >= 80 ? ' is-hot' : ''}`;
  $('spend-label').textContent = `$${spent.toFixed(2)} of $${budget.toFixed(0)}`;
  const meter = $('spend-meter');
  meter.setAttribute('aria-valuenow', spent.toFixed(4));
  meter.setAttribute('aria-valuemax', String(budget));
  meter.setAttribute('aria-valuetext', `$${spent.toFixed(4)} of $${budget.toFixed(2)} used`);
}

function paintSummary() {
  const submitted = state.attempts.filter((item) => item.result);
  const incorrect = submitted.filter((item) => !item.result.correct_action).length;
  const safePauses = submitted.filter((item) => item.result.paused && item.result.safe_handling).length;
  const rows = [
    ['Independent completions', String(state.summary.independent), `of ${state.summary.completed} submitted`],
    ['Incorrect decisions', String(incorrect), 'of submitted decisions'],
    ['Expert contacts', String(state.summary.expert_contacts), 'direct requests in this session'],
    ['Open requests', String(state.summary.open_gaps), 'still unanswered'],
    ['Approved cards', String(state.summary.approved_guidance), 'available to later cases'],
    ['Safe pauses', String(safePauses), 'held without an incorrect accept'],
    ['Attacks held', String(state.summary.attacks_held), state.summary.attacks ? `of ${state.summary.attacks} generated orders` : 'not run yet'],
  ];
  $('summary').replaceChildren(...rows.map(([label, value, hint]) => {
    const card = document.createElement('div');
    card.className = 'metric';
    card.append(text('strong', value), text('span', label), text('small', hint));
    return card;
  }));
  const transferDone = state.attempts.some((item) => (item.case.split === 'transfer' || item.case.split === 'boundary') && item.result);
  $('summary-note').textContent = transferDone
    ? 'Counts come from this session’s saved attempts. Cases differ, so this is not a role score.'
    : 'No transfer tests completed yet.';
}

function paintHistory() {
  if (!state.attempts.length) {
    $('history').replaceChildren(text('p', 'No attempts yet. Start a case to record the first step.'));
  } else {
    $('history').replaceChildren(...[...state.attempts].reverse().map((item) => {
      const count = item.actions.length;
      const button = text('button', `${item.case.case_id} · ${item.status.replaceAll('_', ' ')} · ${count} ${count === 1 ? 'step' : 'steps'}`);
      button.type = 'button';
      button.className = 'secondary';
      button.setAttribute('aria-pressed', String(item.id === selectedId));
      button.onclick = () => {
        selectedId = item.id;
        clean();
        render();
      };
      return button;
    }));
  }
  $('timeline').replaceChildren();
  if (!active) return;
  $('timeline').append(text('h3', `Recorded steps · ${active.case.case_id}`));
  if (!active.actions.length) {
    $('timeline').append(text('p', 'No decision recorded yet.'));
    return;
  }
  for (const action of active.actions) {
    const card = document.createElement('div');
    card.className = 'trail';
    const sources = action.evidence_refs.join(', ') || 'None recorded (earlier attempt)';
    card.append(
      text('strong', action.action.replaceAll('_', ' ')),
      text('p', action.reason),
      text('small', `${new Date(action.created).toLocaleString()} · Sources: ${sources}`),
    );
    $('timeline').append(card);
  }
}

function paintAttacks() {
  const pending = Boolean(state.summary.pending_attack);
  const ready = state.summary.approved_guidance > 0;
  $('attack').dataset.keepDisabled = ready && !pending ? 'false' : 'true';
  $('attack').disabled = working || $('attack').dataset.keepDisabled === 'true';
  const host = state.attempts.find((item) => item.gaps.some((gap) => gap.status === 'open' && gap.question.startsWith('Attack:')));
  $('attack-note').textContent = pending
    ? 'A failed attack is waiting for a tighter card. The previous card stays approved until that wording is approved.'
    : ready
      ? 'The model sees the approved substitution card and the orders already used. It does not see the hidden rule. The grader runs after the model answers.'
      : 'Approve a substitution card first. Then the model will invent orders that try to break it.';
  const labels = {held: 'Card held', too_vague: 'Card too vague', wrong: 'Card was wrong'};
  const conditions = {
    wrong_certificate: 'Wrong certificate',
    missing_certificate: 'Missing certificate',
    lookalike_revision: 'Lookalike revision',
  };
  const cards = state.attacks.map((item) => {
    const card = document.createElement('article');
    card.className = `attack-card ${item.verdict}`;
    const facts = Object.entries(item.facts).map(([key, value]) => `${key.replaceAll('_', ' ')}: ${value === null ? 'missing' : value}`).join(' · ');
    card.append(
      text('strong', `${conditions[item.condition] || item.condition} · ${labels[item.verdict] || item.verdict}`),
      text('p', item.note),
      text('p', facts),
      text('small', `Card suggested ${item.suggested_action.replaceAll('_', ' ')}. Grader required ${item.graded_action.replaceAll('_', ' ')}.`),
    );
    return card;
  });
  if (host && host.id !== active?.id) {
    const jump = text('button', `Open ${host.case.case_id} to tighten the card`);
    jump.type = 'button';
    jump.className = 'secondary';
    jump.onclick = () => {
      selectedId = host.id;
      render();
      $('capture').scrollIntoView({block: 'center'});
    };
    cards.unshift(jump);
  }
  $('attacks').replaceChildren(...(cards.length ? cards : [text('p', 'No attacks yet.')]));
}

function render() {
  const choice = $('case').value;
  fillCases(choice);
  $('handbook').replaceChildren(...state.handbook.map((line) => text('li', line)));
  $('model-note').textContent = state.model_status === 'ready'
    ? `${state.provider === 'baseten' ? 'Baseten' : 'Meta'} · ${state.model_name}. $${Number(state.spend.spent_usd).toFixed(4)} of $${Number(state.spend.budget_usd).toFixed(0)} used.`
    : state.setup_message;
  paintSpend();
  $('guidance-count').textContent = state.summary.approved_guidance
    ? `${state.summary.approved_guidance} expert card${state.summary.approved_guidance === 1 ? '' : 's'} approved in this session.`
    : 'Version 1 · No expert-approved guidance yet.';
  active = state.attempts.find((item) => item.id === selectedId) || state.attempts.at(-1);
  selectedId = active ? active.id : null;
  remember('mm-active', selectedId || '');
  const savedDraft = active ? draft() : {};
  pending = savedDraft.pending || null;
  const checked = new Set(savedDraft.refs || []);
  $('reason').value = savedDraft.reason || '';
  $('expert-answer').value = savedDraft.expert || '';
  $('action').value = savedDraft.action || 'ask_expert';
  $('category').value = savedDraft.category || 'knowledge';
  categoryVisibility();
  $('draft-status').textContent = savedDraft.reason ? 'Draft restored from this device.' : '';
  $('boot').hidden = true;
  $('empty').hidden = Boolean(active);
  $('empty').textContent = 'Start a practice case to see which decisions the handbook supports.';
  $('mission').hidden = !active;
  // Workbench steps: step 1 (evidence) lives outside #decision, so hide it explicitly when empty
  for (const step of document.querySelectorAll('#workbench .wb-step')) step.hidden = !active;
  $('facts').replaceChildren();
  $('evidence-list').replaceChildren();
  $('result').replaceChildren();
  $('result').className = '';
  $('decision').hidden = !active || Boolean(active.result);
  // When decision is hidden, its inner wb-steps are also hidden via the form — keep step-heads from showing orphaned
  for (const step of document.querySelectorAll('#decision .wb-step')) step.hidden = $('decision').hidden;
  $('gap-panel').hidden = !active?.gaps.length;
  $('gaps').replaceChildren();
  $('capture').hidden = true;
  $('fresh').hidden = true;
  $('fresh').classList.remove('is-boundary');
  $('case-title').hidden = !active;
  $('citations').replaceChildren(text('legend', 'Which opened sources support your next step?'));
  markStages(stageFor(active));
  $('title').textContent = active
    ? `${state.split_labels[active.case.split] || 'Order'} ${active.case.case_id}`
    : 'Ready for Monday?';
  if (!active) $('diagnosis').hidden = true;
  if (active) {
    $('case-title').textContent = `${state.family_labels[active.case.family] || active.case.family} · ${active.case.title}`;
    if (active.case.split === 'transfer' || active.case.split === 'boundary') {
      $('fresh').hidden = false;
      $('fresh').classList.toggle('is-boundary', active.case.split === 'boundary');
      $('fresh').textContent = active.case.split === 'transfer'
        ? 'Fresh order in the same family. Use only the handbook and guidance approved in this session.'
        : 'Boundary order. Approved guidance from this session is available. It may not cover this order.';
    }
    for (const [key, value] of Object.entries(active.case.facts)) {
      $('facts').append(text('dt', key.replaceAll('_', ' ')), text('dd', value === null ? 'Not provided' : String(value)));
    }
    // Step heading now in HTML (.wb-step-head); no JS-injected h3 needed
    for (const item of active.evidence) {
      const viewed = active.inspected.includes(item.id);
      const button = text('button', `${viewed ? '✓ Opened' : 'Open'} · ${item.title}`);
      button.type = 'button';
      button.className = viewed ? 'evidence-button secondary is-open' : 'evidence-button secondary';
      button.setAttribute('aria-pressed', String(viewed));
      button.onclick = () => busy(button, async () => {
        const doc = await api('/api/inspect', {attempt_id: active.id, evidence_id: item.id});
        await refresh();
        $('document-title').textContent = doc.title;
        $('document-content').replaceChildren(...doc.content.map((line) => text('li', line)));
        $('document').hidden = false;
      });
      $('evidence-list').append(button);
      if (viewed) {
        const label = document.createElement('label');
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.value = item.id;
        input.checked = checked.has(item.id);
        label.append(input, document.createTextNode(item.title));
        $('citations').append(label);
      }
    }
    $('checkpoint').textContent = active.inspected.length
      ? '2. Explain your next step and cite the evidence you opened. Opening a source records exposure, not understanding.'
      : 'Open a source above before recording a decision. Check the exception guidance if the handbook does not cover this order.';
    if (active.result) {
      const outcome = active.result;
      const fresh = active.case.split === 'transfer' || active.case.split === 'boundary';
      const decision = active.actions.find((item) => item.action !== 'ask_expert');
      const boundaryStop = outcome.correct_action && active.case.split === 'boundary' && decision && decision.action === 'reject';
      const line = boundaryStop
        ? 'This order is outside the approved card, and it was not accepted.'
        : outcome.independent_completion && fresh
          ? 'This fresh order was completed from the approved card. No expert was called on this attempt.'
          : outcome.independent_completion
            ? 'Your action matches the case, without a recorded expert request.'
            : outcome.correct_action
              ? 'Your next step matches the case. The task was not completed independently.'
              : outcome.safe_handling
                ? 'You paused the task. It remains unresolved.'
                : outcome.paused
                  ? 'This pause was not the next step the evidence supports.'
                  : 'Your decision does not meet this case. The approved card does not make an excluded order acceptable.';
      const verdict = boundaryStop || (outcome.independent_completion && fresh)
        ? 'verdict-pass'
        : outcome.correct_action || outcome.safe_handling
          ? 'verdict-hold'
          : 'verdict-miss';
      $('result').className = verdict;
      $('result').append(text('strong', fresh ? 'Handover check' : 'Practice debrief'), text('p', line));
      if (outcome.independent_completion && !boundaryStop) $('result').append(text('p', 'Demonstrated on this case.'));
      const last = active.actions.at(-1);
      $('result').append(text('p', `Your decision: ${last.action.replaceAll('_', ' ')}. Reason: ${last.reason}`));
    }
    for (const gap of active.gaps) {
      const card = document.createElement('div');
      card.className = 'gap';
      const label = {open: 'Open', approved: 'Approved for later cases', rejected: 'Rejected'}[gap.status] || gap.status;
      card.append(text('strong', gap.category.replaceAll('_', ' ')), text('p', gap.question), text('small', label));
      $('gaps').append(card);
    }
    const openGap = active.gaps.find((gap) => gap.status === 'open' && (gap.category === 'knowledge' || gap.category === 'unknown'));
    if (openGap) {
      $('capture').hidden = false;
      $('capture-question').textContent = openGap.question;
    }
    const diagnosis = active.diagnosis;
    $('diagnosis').hidden = !diagnosis;
    if (diagnosis) {
      $('diagnosis').replaceChildren(
        text('strong', `Diagnosis · ${diagnosis.category.replaceAll('_', ' ')}`),
        text('p', diagnosis.missing_distinction),
        text('p', diagnosis.expert_question),
        text('small', `Suggested next step: ${diagnosis.suggested_action.replaceAll('_', ' ')}. ${diagnosis.uncertainties.join(' ')}`),
      );
    }
  }
  paintSummary();
  paintAttacks();
  paintHistory();
  if (working) lock(true);
  else {
    $('start').disabled = false;
    $('new').disabled = false;
  }
}

$('start').onclick = () => busy($('start'), async () => {
  selectedId = (await api('/api/attempts', {case_id: $('case').value})).attempt_id;
  clean();
  await refresh();
});

$('new').onclick = () => busy($('new'), async () => {
  if (!confirm('Start a new session? Existing attempts remain saved locally.')) return;
  sid = (await api('/api/sessions', {})).session_id;
  if (!remember('mm-session', sid)) toast('This browser could not store the session. Keep this tab open.');
  selectedId = null;
  clean();
  await refresh();
  toast('New session ready. Earlier sessions stay in the local database.');
});

$('decision').onsubmit = (event) => {
  event.preventDefault();
  busy($('save'), async () => {
    const refs = [...$('citations').querySelectorAll('input:checked')].map((box) => box.value);
    if (!refs.length) throw new Error('Open and select at least one source before saving.');
    const payload = {
      attempt_id: active.id,
      action: $('action').value,
      reason: $('reason').value,
      evidence_refs: refs,
      category: $('category').value,
    };
    const signature = JSON.stringify(payload);
    if (!pending || pending.signature !== signature) pending = {signature, id: crypto.randomUUID()};
    saveDraft();
    await api('/api/actions', {...payload, id: pending.id});
    pending = null;
    remember(draftsKey(), '{}');
    await refresh();
    $('reason').value = '';
    toast('Next step saved in this session.');
    if (!$('capture').hidden) $('capture').scrollIntoView({block: 'center'});
  });
};

$('decision').addEventListener('input', saveDraft);
$('decision').addEventListener('change', () => { categoryVisibility(); saveDraft(); });

async function review(decision, answer = $('expert-answer').value) {
  if (!active) return;
  const data = await api('/api/guidance', {attempt_id: active.id, answer, decision});
  if (data.needs_review) {
    $('review-note').textContent = data.message;
    return;
  }
  $('review-note').textContent = data.abstained
    ? 'No card was published. Not knowing is a recorded answer.'
    : data.premise
      ? 'The scenario note was saved. No card was published.'
      : '';
  if (data.published) toast('Approved. Later cases in this session can open this card.');
  else if (!data.abstained && !data.premise) toast('Rejected. Nothing was published.');
  $('expert-answer').value = '';
  saveDraft();
  await refresh();
}

$('diagnose').onclick = () => busy($('diagnose'), async () => {
  if (!active) return;
  const data = await api('/api/diagnose', {attempt_id: active.id});
  $('reason').value = data.expert_question;
  $('action').value = data.suggested_action;
  if ([...$('category').options].some((option) => option.value === data.category)) $('category').value = data.category;
  categoryVisibility();
  saveDraft();
  await refresh();
  toast('Diagnosis ready. Nothing is saved until you submit it.');
});

$('suggest').onclick = () => busy($('suggest'), async () => {
  if (!active) return;
  const data = await api('/api/suggest', {attempt_id: active.id});
  $('reason').value = data.reason;
  $('action').value = data.action;
  categoryVisibility();
  saveDraft();
  await refresh();
  toast('Suggestion ready. It is not saved until you submit it.');
});

$('draft').onclick = () => busy($('draft'), async () => {
  if (!active) return;
  const data = await api('/api/draft', {attempt_id: active.id, answer: $('expert-answer').value});
  $('expert-answer').value = data.card;
  saveDraft();
  await refresh();
  toast('Draft ready. Approve this exact wording to publish it.');
});

$('attack').onclick = () => busy($('attack'), async () => {
  const data = await api('/api/attack', {});
  if (data.draft_created) selectedId = data.attempt_id;
  await refresh();
  (data.draft_created ? $('capture') : $('attack-panel')).scrollIntoView({block: 'center'});
  toast(data.draft_created
    ? 'The card failed an attack. The previous version stays approved until you approve a tighter one.'
    : 'The card held on these attacks.');
});

$('approve').onclick = () => busy($('approve'), () => review('approve'));
$('reject').onclick = () => busy($('reject'), () => review('reject'));
$('unknown').onclick = () => busy($('unknown'), () => review('abstain', "I don't know"));
$('premise').onclick = () => busy($('premise'), () => review('premise', $('expert-answer').value.trim() || 'This scenario is unrealistic.'));
$('expert-answer').addEventListener('input', saveDraft);

(async () => {
  try {
    if (!sid) {
      sid = (await api('/api/sessions', {})).session_id;
      if (!remember('mm-session', sid)) toast('This browser could not store the session. Keep this tab open.');
    }
    try {
      await refresh();
    } catch (err) {
      if (err.status !== 404) throw err;
      sid = (await api('/api/sessions', {})).session_id;
      remember('mm-session', sid);
      selectedId = null;
      await refresh();
      error(new Error('The previous session is no longer available in this database. A new session is ready.'));
    }
  } catch (err) {
    $('boot').hidden = true;
    error(err);
  }
})();
