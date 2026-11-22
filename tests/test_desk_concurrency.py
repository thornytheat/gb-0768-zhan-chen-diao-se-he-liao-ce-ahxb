from concurrent.futures import ThreadPoolExecutor

from app.main import create_app


def _client(directory):
    return create_app(directory).test_client()


def test_opposing_concurrent_reviews_filingsettle_into_one_decision(tmp_path):
    directory = str(tmp_path)
    key = _client(directory).post('/api/books', json={'sample': 'dispute'}).json['key']

    def call(decision):
        client = _client(directory)
        response = client.post(f'/api/desk/{key}/review', json={'pot': 'A12', 'decision': decision})
        return response.status_code, response.json.get('code')

    with ThreadPoolExecutor(2) as executor:
        results = list(executor.map(call, ['confirm', 'reject']))
    assert sorted(results) == [(200, None), (409, 'REVIEW_CONFLICT')]
    decisions = _client(directory).get(f'/api/desk/{key}').json['decisions']
    assert list(decisions) == ['A12']
    assert decisions['A12']['decision'] in {'confirm', 'reject'}


def test_concurrent_identical_reviews_create_one_record(tmp_path):
    directory = str(tmp_path)
    key = _client(directory).post('/api/books', json={'sample': 'dispute'}).json['key']

    def call(_):
        client = _client(directory)
        return client.post(f'/api/desk/{key}/review',
                           json={'pot': 'B08', 'decision': 'confirm'}).json['reused']

    with ThreadPoolExecutor(2) as executor:
        reused = list(executor.map(call, range(2)))
    assert sorted(reused) == [False, True]


def test_concurrent_signing_emits_one_receipt(tmp_path):
    directory = str(tmp_path)
    key = _client(directory).post('/api/books', json={'sample': 'dispute'}).json['key']

    def sign(_):
        client = _client(directory)
        body = client.post(f'/api/desk/{key}/sign', json={'pot': 'T20'}).json
        return body['reused'], body['receipt']['receipt_id']

    with ThreadPoolExecutor(2) as executor:
        results = list(executor.map(sign, range(2)))
    assert len({rid for _, rid in results}) == 1
    assert sorted(reused for reused, _ in results) == [False, True]
    receipts = _client(directory).get(f'/api/receipts/{key}').json['receipts']
    assert [r['pot'] for r in receipts] == ['T20']


def test_dossier_state_survives_app_restart(tmp_path):
    directory = str(tmp_path)
    client = _client(directory)
    key = client.post('/api/books', json={'sample': 'dispute'}).json['key']
    client.post(f'/api/desk/{key}/review', json={'pot': 'A12', 'decision': 'confirm'})
    receipt = client.post(f'/api/desk/{key}/sign', json={'pot': 'T20'}).json['receipt']

    restarted = _client(directory)
    desk = restarted.get(f'/api/desk/{key}').json
    assert desk['decisions']['A12']['status'] == 'CONFIRMED'
    assert restarted.get(f"/api/receipts/{key}/{receipt['receipt_id']}").json['sha256'] == receipt['sha256']


def test_receipt_id_is_deterministic_per_book_and_pot():
    from app.ledger.dossier import receipt_id
    assert receipt_id('book', 'A12') == receipt_id('book', 'A12')
    assert receipt_id('book', 'A12') != receipt_id('book', 'B08')
    assert receipt_id('book', 'A12') != receipt_id('other', 'A12')
