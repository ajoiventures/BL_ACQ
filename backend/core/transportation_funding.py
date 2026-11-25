"""Source-reported funding reconciliation. Not a funding or delivery authorization."""
from decimal import Decimal, InvalidOperation


def money(value):
    if not isinstance(value, str):
        raise ValueError('money must be an exact decimal string')
    try:
        n = Decimal(value)
        if not n.is_finite() or n < 0 or n.quantize(Decimal('0.01')) != n:
            raise ValueError('invalid amount')
        return n.quantize(Decimal('0.01'))
    except InvalidOperation as exc:
        raise ValueError('invalid amount') from exc


def reconcile_funding(packet):
    """Reconcile components only within one declared source and scope.

    Do not sum estimates across scopes or interpret an arithmetic match as
    an obligation, disbursement, available funds or construction progress.
    """
    seen = set()
    results = []
    for item in packet:
        keys = ('record_id', 'source_id', 'scope_id', 'basis')
        if any(not isinstance(item.get(k), str) or not item[k].strip() for k in keys):
            raise ValueError('missing scope or provenance')
        if item['record_id'] in seen:
            raise ValueError('duplicate funding observation')
        seen.add(item['record_id'])
        total = money(item['total_usd'])
        components = item.get('components', [])
        ids = [c['id'] for c in components]
        if any(not isinstance(i,str) or not i.strip() for i in ids) or len(set(ids)) != len(ids):
            raise ValueError('invalid or duplicate component')
        if any(c.get('scope_id') != item['scope_id'] or c.get('source_id') != item['source_id'] for c in components):
            raise ValueError('component scope or source mismatch')
        component_sum = sum((money(c['usd']) for c in components), Decimal('0.00')) if components else None
        residual = total-component_sum if component_sum is not None else None
        results.append({'record_id':item['record_id'],'scope_id':item['scope_id'],'basis':item['basis'],
            'total_usd':str(total),'components_sum_usd':str(component_sum) if component_sum is not None else None,
            'arithmetic_difference_usd':str(residual) if residual is not None else None,
            'arithmetic_status':'NOT_TESTABLE_NO_COMPONENTS' if residual is None else 'BALANCED' if residual==0 else 'REVIEW_DIFFERENCE',
            'funds_obligated_usd':None,'funds_disbursed_usd':None,'construction_complete':None})
    return {'observations':results,'cross_scope_total_usd':None,'market_effect':None,'authorization':False}
