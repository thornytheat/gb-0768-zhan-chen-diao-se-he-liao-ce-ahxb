import pytest


@pytest.fixture
def sealed(client):
    return client.post('/api/books', json={'sample': 'dispute'}).json['key']


def test_ready_pot_can_be_signed_first_without_review(client, sealed):
    result = client.post(f'/api/desk/{sealed}/sign', json={'pot': 'T20'})
    assert result.status_code == 200
    receipt = result.json['receipt']
    assert result.json['reused'] is False
    assert receipt['basis'] == 'uncontested' and receipt['pot'] == 'T20'
    assert client.get(f'/api/desk/{sealed}').json['issuance']['pots']
    status = next(p for p in client.get(f'/api/desk/{sealed}').json['issuance']['pots'] if p['pot'] == 'T20')
    assert status['status'] == 'SIGNED'


def test_held_pot_cannot_be_signed_before_review(client, sealed):
    response = client.post(f'/api/desk/{sealed}/sign', json={'pot': 'A12'})
    assert (response.status_code, response.json['code']) == (422, 'POT_HELD')


def test_review_confirm_releases_pot_and_counts_it_into_inventory(client, sealed):
    response = client.post(f'/api/desk/{sealed}/review', json={'pot': 'A12', 'decision': 'confirm'})
    assert response.status_code == 200 and response.json['reused'] is False
    desk = client.get(f'/api/desk/{sealed}').json['issuance']
    pot = next(p for p in desk['pots'] if p['pot'] == 'A12')
    assert pot['status'] == 'CONFIRMED'
    assert desk['confirmed_totals']['opening_mg'] == 100000
    signed = client.post(f'/api/desk/{sealed}/sign', json={'pot': 'A12'})
    assert signed.json['receipt']['basis'] == 'review_confirmed'


def test_review_reject_keeps_pot_out_of_inventory_and_blocks_signing(client, sealed):
    client.post(f'/api/desk/{sealed}/review', json={'pot': 'B08', 'decision': 'reject'})
    blocked = client.post(f'/api/desk/{sealed}/sign', json={'pot': 'B08'})
    assert (blocked.status_code, blocked.json['code']) == (422, 'POT_REJECTED')
    desk = client.get(f'/api/desk/{sealed}').json['issuance']
    assert next(p for p in desk['pots'] if p['pot'] == 'B08')['status'] == 'REJECTED'
    assert desk['confirmed_totals']['issued_mg'] == 20002


def test_same_review_retry_is_idempotent(client, sealed):
    first = client.post(f'/api/desk/{sealed}/review', json={'pot': 'A12', 'decision': 'confirm'})
    second = client.post(f'/api/desk/{sealed}/review', json={'pot': 'A12', 'decision': 'confirm'})
    assert (first.json['reused'], second.json['reused']) == (False, True)
    assert first.json['decision'] == second.json['decision']


def test_opposing_review_cannot_each_be_filed(client, sealed):
    client.post(f'/api/desk/{sealed}/review', json={'pot': 'A12', 'decision': 'confirm'})
    conflict = client.post(f'/api/desk/{sealed}/review', json={'pot': 'A12', 'decision': 'reject'})
    assert (conflict.status_code, conflict.json['code']) == (409, 'REVIEW_CONFLICT')
    decision = client.get(f'/api/desk/{sealed}').json['decisions']['A12']
    assert decision['decision'] == 'confirm'


def test_retry_signing_returns_same_receipt(client, sealed):
    first = client.post(f'/api/desk/{sealed}/sign', json={'pot': 'T20'}).json['receipt']
    second = client.post(f'/api/desk/{sealed}/sign', json={'pot': 'T20'}).json
    assert second['reused'] is True and second['receipt']['receipt_id'] == first['receipt_id']
    receipts = client.get(f'/api/receipts/{sealed}').json['receipts']
    assert len(receipts) == 1 and receipts[0]['receipt_id'] == first['receipt_id']


def test_signed_receipt_remains_retrievable(client, sealed):
    receipt = client.post(f'/api/desk/{sealed}/sign', json={'pot': 'T20'}).json['receipt']
    fetched = client.get(f"/api/receipts/{sealed}/{receipt['receipt_id']}")
    assert fetched.status_code == 200 and fetched.json['sha256'] == receipt['sha256']
    assert client.get(f"/api/receipts/{sealed}/{'0' * 16}").status_code == 404


def test_clean_pot_cannot_be_reviewed(client, sealed):
    response = client.post(f'/api/desk/{sealed}/review', json={'pot': 'T21', 'decision': 'confirm'})
    assert (response.status_code, response.json['code']) == (422, 'POT_NOT_HELD')


def test_unknown_pot_and_bad_decision_are_rejected(client, sealed):
    assert client.post(f'/api/desk/{sealed}/sign', json={'pot': 'ZZZ'}).status_code == 404
    bad = client.post(f'/api/desk/{sealed}/review', json={'pot': 'A12', 'decision': 'maybe'})
    assert (bad.status_code, bad.json['code']) == (400, 'REVIEW_INVALID')


def test_desk_requires_existing_book(client):
    assert client.get(f"/api/desk/{'a' * 64}").status_code == 404
