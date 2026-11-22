from collections import Counter, defaultdict

FLOW = {'OPEN': 'opening_mg', 'ISSUE': 'issued_mg', 'APPLY': 'applied_mg',
        'LOSS': 'loss_mg', 'RETURN': 'returned_mg'}
FLOW_FIELDS = (*FLOW.values(), 'disputed_mg')
# 挂起罐的推算成分一律不计入确认库存与签发收据，复核确认后才放行。
HOLD_REASONS = {'TICKET_SPLIT': '同号称量票指向多罐', 'PENDING_MATERIAL': '期末仍有留罐争议'}


def _split_groups(weighings):
    groups = defaultdict(list)
    for row in weighings['isolated']:
        if row['code'] == 'TICKET_SPLIT':
            groups[row['data']['ticket']].append(row)
    return dict(sorted(groups.items()))


def build_desk(job):
    """按罐汇总签发状态。挂起罐的推算回桶成分只作展示，不进确认库存。"""
    weighings, recovery, balance = job.weighings, job.recovery, job.balance
    splits = _split_groups(weighings)
    split_pots = defaultdict(list)
    for ticket, rows in splits.items():
        for row in rows:
            split_pots[row['data']['pot']].append(ticket)

    pending = recovery['pending_mg']
    all_pots = sorted({*(row['data']['pot'] for row in recovery['rows']),
                       *(row['data']['pot'] for group in splits.values() for row in group),
                       *pending})

    flows = defaultdict(Counter)
    for row in recovery['rows']:
        action = row['data']['action']
        for lot, amount in row['parts_mg'].items():
            flows[row['data']['pot']][(lot, FLOW[action])] += amount
    for pot, lots in pending.items():
        for lot, amount in lots.items():
            flows[pot][(lot, 'disputed_mg')] += amount

    claim_index = {line['lot']: line for line in balance['lines']}
    pots = []
    for pot in all_pots:
        reasons = []
        if pot in split_pots:
            reasons.append('TICKET_SPLIT')
        if pending.get(pot):
            reasons.append('PENDING_MATERIAL')
        held = bool(reasons)
        lots = sorted({lot for (lot, _) in flows[pot]})
        lot_lines = []
        for lot in lots:
            values = {key: flows[pot][(lot, key)] for key in FLOW_FIELDS}
            claim = claim_index.get(lot)
            lot_lines.append({
                'lot': lot,
                **values,
                'check_mg': values['opening_mg'] + values['issued_mg']
                           - values['applied_mg'] - values['loss_mg']
                           - values['returned_mg'] - values['disputed_mg'],
                'claimed_mg': claim['claimed_mg'] if claim else None,
                'difference_mg': claim['difference_mg'] if claim else None,
                'claim_code': claim['code'] if claim else 'NO_CLAIM',
            })
        pots.append({
            'pot': pot,
            'status': 'HELD' if held else 'READY',
            'hold_reasons': reasons,
            'hold_labels': [HOLD_REASONS[code] for code in reasons],
            'split_tickets': sorted(set(split_pots.get(pot, ()))),
            'pending_mg': dict(pending.get(pot, {})),
            'lot_lines': lot_lines,
            'totals': {key: sum(line[key] for line in lot_lines) for key in FLOW_FIELDS},
        })

    # 确认库存只汇总当前未挂起的罐；挂起罐复核确认后才计入。
    confirmed = {key: 0 for key in FLOW_FIELDS}
    for pot in pots:
        if pot['status'] != 'HELD':
            for key in FLOW_FIELDS:
                confirmed[key] += pot['totals'][key]
    return {
        'pots': pots,
        'split_groups': [
            {'ticket': ticket,
             'pots': sorted({row['data']['pot'] for row in rows}),
             'lines': [{'line': row['line'], 'pot': row['data']['pot'],
                        'container': row['data']['container'],
                        'gross': row['data']['gross'], 'unit': row['data']['unit'],
                        'received_utc': row['received_utc']} for row in rows]}
            for ticket, rows in splits.items()
        ],
        'confirmed_totals': confirmed,
        'held_pots': [pot['pot'] for pot in pots if pot['status'] == 'HELD'],
        'ready_pots': [pot['pot'] for pot in pots if pot['status'] == 'READY'],
    }
