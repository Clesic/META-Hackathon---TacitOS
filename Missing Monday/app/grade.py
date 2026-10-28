"""Local outcome grader. This is the fixture oracle. Never send it to a model."""
from __future__ import annotations


def grade(case: dict) -> str:
    facts = case['facts']
    family = case['family']
    if family == 'standard':
        if not facts.get('access'):
            return 'report_permission_issue'
        if facts.get('documents_complete') is not True:
            return 'request_evidence'
        return 'accept' if facts.get('part_matches') else 'escalate'
    if family == 'substitution':
        if (facts.get('supplier'), facts.get('ordered_part'), facts.get('offered_part')) != ('Northline', 'P-100', 'P-100B'):
            return 'escalate'
        if facts.get('machine_revision') is None or facts.get('certificate') is None:
            return 'request_evidence'
        return 'accept' if facts['machine_revision'] in ('R2', 'R3') and facts['certificate'] == 'C-B' else 'reject'
    if family == 'duplicate':
        if facts.get('supplier') != 'Westhaven':
            return 'escalate'
        if any(facts.get(key) in (None, '') for key in ('order_kind', 'original_status', 'replacement_reference')):
            return 'request_evidence'
        return 'accept' if facts['order_kind'] == 'replacement' and facts['original_status'] == 'cancelled' else 'reject'
    if family == 'delivery':
        if facts.get('supplier') != 'Eastbridge' or facts.get('delivery_mode') != 'split':
            return 'escalate'
        if any(facts.get(key) is None for key in ('first_batch_units', 'minimum_start_units', 'remaining_delivery_before_deadline')):
            return 'request_evidence'
        return 'accept' if facts['first_batch_units'] >= facts['minimum_start_units'] and facts['remaining_delivery_before_deadline'] is True else 'reject'
    raise ValueError(f'Unknown family: {family}')
