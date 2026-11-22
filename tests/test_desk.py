from app.web import LINKS


def test_workbench_and_every_module_page(client):
    assert '克重收据' in client.get('/').get_data(as_text=True)
    for slug,label in LINKS.items():
        response=client.get('/studio/'+slug)
        assert response.status_code==200 and f'<h1>{label}</h1>' in response.get_data(as_text=True)


def test_backed_receipt_links_to_signed_artifact(client):
    key=client.post('/api/books',json={'sample':'dirty'}).json['key']
    assert f'href="/api/export/{key}"' in client.get('/studio/receipt?key='+key).get_data(as_text=True)


def test_failed_preview_has_explanation(client):
    response=client.get('/api/trial/unlisted/tares')
    assert (response.status_code,response.json['code'])==(404,'SAMPLE_ABSENT')


def test_issuance_desk_shows_held_and_ready_pots(client):
    page=client.get('/studio/issuance?sample=dispute').get_data(as_text=True)
    assert '分罐签发工作台' in page and '同号称量票争议原件' in page
    assert '挂起待复核' in page and '可先签' in page
    assert '封存后才能复核与签发' in page


def test_backed_issuance_desk_offers_review_actions(client):
    key=client.post('/api/books',json={'sample':'dispute'}).json['key']
    page=client.get('/studio/issuance?key='+key).get_data(as_text=True)
    assert 'desk-review' in page and 'desk-sign' in page
