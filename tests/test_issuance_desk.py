from app.job import MixingJob
from app.receipts.packet import read_sample


def test_same_ticket_pointing_at_two_pots_is_split_not_conflict():
    job = MixingJob(read_sample('dispute'))
    split = [r for r in job.weighings['isolated'] if r['code'] == 'TICKET_SPLIT']
    assert {(r['data']['ticket'], r['data']['pot'], r['line']) for r in split} == {
        ('0005', 'A12', 6), ('0005', 'B08', 9)}
    assert not any(r['data']['ticket'] == '0005' for r in job.weighings['tickets'])
    assert not any(r['code'] == 'TICKET_CONFLICT' for r in job.weighings['isolated'])


def test_split_tickets_keep_both_originals_out_of_replay():
    job = MixingJob(read_sample('dispute'))
    rebuilt = {r['data']['ticket'] for r in job.recovery['rows']}
    assert '0005' not in rebuilt


def test_desk_marks_only_disputed_pots_held():
    desk = MixingJob(read_sample('dispute')).issuance
    assert desk['held_pots'] == ['A12', 'B08']
    assert desk['ready_pots'] == ['T20', 'T21']
    by_pot = {p['pot']: p for p in desk['pots']}
    assert by_pot['A12']['hold_reasons'] == ['TICKET_SPLIT', 'PENDING_MATERIAL']
    assert by_pot['A12']['split_tickets'] == ['0005']
    assert by_pot['T20']['status'] == 'READY' and by_pot['T20']['hold_reasons'] == []


def test_held_pot_estimated_composition_excluded_from_confirmed_totals():
    desk = MixingJob(read_sample('dispute')).issuance
    # 确认库存只含 T20/T21 两只无争议罐，每罐领用与回桶各 10001 mg。
    assert desk['confirmed_totals'] == {'opening_mg': 0, 'issued_mg': 20002,
                                        'applied_mg': 0, 'loss_mg': 0,
                                        'returned_mg': 20002, 'disputed_mg': 0}


def test_split_group_carries_both_raw_rows():
    groups = MixingJob(read_sample('dispute')).issuance['split_groups']
    assert len(groups) == 1
    group = groups[0]
    assert group['ticket'] == '0005' and group['pots'] == ['A12', 'B08']
    assert [r['line'] for r in group['lines']] == [6, 9]


def test_clean_sample_has_no_held_pots():
    desk = MixingJob(read_sample('clean')).issuance
    assert desk['held_pots'] == [] and desk['split_groups'] == []
    assert {p['pot'] for p in desk['pots']} == {'A12', 'B08', *(f'T2{i}' for i in range(10))}
