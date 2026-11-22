from flask import Blueprint,current_app,jsonify,request

from app.faults import LedgerError
from app.job import MixingJob,VIEWS
from app.ledger.closeout import close
from app.ledger.dossier import Dossier
from app.ledger.signoff import certify
from app.receipts.packet import read_sample

api=Blueprint('palette',__name__,url_prefix='/api')


def bookshelf():
    return current_app.extensions['receipt_bookshelf']


def dossier_for(key):
    bookshelf().require(key)
    return Dossier(bookshelf(),key)


def desk_payload(key):
    record=bookshelf().require(key)
    dossier=Dossier(bookshelf(),key)
    state=dossier.view()
    signed={item['pot']:item for item in state['receipts']}
    pots=[]
    for pot in record['snapshot']['issuance']['pots']:
        item=dict(pot)
        decision=state['decisions'].get(pot['pot'])
        if pot['pot'] in signed:
            item['status']='SIGNED'
            item['receipt']=signed[pot['pot']]
        elif decision is not None:
            item['status']=decision['status']
            item['decision']=decision
        pots.append(item)
    # 已确认的挂起罐解除挂起，其重量计入确认库存；被驳回的仍排除。
    confirmed=dict(record['snapshot']['issuance']['confirmed_totals'])
    for item in pots:
        if item['status']=='CONFIRMED':
            for field,amount in item['totals'].items():
                confirmed[field]+=amount
    return {'key':key,'order':record['manifest']['order'],
            'issuance':record['snapshot']['issuance'] | {'pots':pots,'confirmed_totals':confirmed},
            'decisions':state['decisions'],'receipts':state['receipts']}


@api.get('/trial/<sample>/<stage>')
def trial(sample,stage):
    if stage not in VIEWS:
        raise LedgerError('STAGE_ABSENT','没有这项核料工序',404)
    return jsonify(getattr(MixingJob(read_sample(sample)),stage))


@api.route('/books',methods=['GET','POST'])
def books():
    book=bookshelf()
    if request.method=='GET':
        return jsonify(books=book.listing())
    record,reused=close(book,request.get_json(silent=True))
    manifest=record['manifest']
    return jsonify(key=manifest['key'],reused=reused,manifest=manifest,totals=record['snapshot']['balance']['totals'])


@api.get('/books/<key>')
def record(key):
    item=bookshelf().require(key)
    return jsonify(manifest=item['manifest'],balance=item['snapshot']['balance'])


@api.get('/export/<key>')
def export(key):
    response=jsonify(certify(bookshelf().require(key)))
    response.headers['Content-Disposition']=f'attachment; filename="palette-{key}.json"'
    return response


@api.get('/desk/<key>')
def desk(key):
    return jsonify(desk_payload(key))


@api.post('/desk/<key>/review')
def review(key):
    body=request.get_json(silent=True) or {}
    pot,decision=body.get('pot'),body.get('decision')
    if not isinstance(pot,str) or not pot.strip():
        raise LedgerError('POT_UNKNOWN','复核请求缺少罐号',400)
    record=bookshelf().require(key)
    held=set(record['snapshot']['issuance']['held_pots'])
    if pot not in {item['pot'] for item in record['snapshot']['issuance']['pots']}:
        raise LedgerError('POT_UNKNOWN',f'找不到罐 {pot}',404)
    if pot not in held:
        raise LedgerError('POT_NOT_HELD',f'罐 {pot} 没有挂起争议，无需复核',422)
    entry,reused=Dossier(bookshelf(),key).review(pot,decision)
    return jsonify(decision=entry,reused=reused,desk=desk_payload(key))


@api.post('/desk/<key>/sign')
def sign(key):
    body=request.get_json(silent=True) or {}
    pot=body.get('pot')
    if not isinstance(pot,str) or not pot.strip():
        raise LedgerError('POT_UNKNOWN','签发请求缺少罐号',400)
    record=bookshelf().require(key)
    desk_pot=next((item for item in record['snapshot']['issuance']['pots'] if item['pot']==pot),None)
    if desk_pot is None:
        raise LedgerError('POT_UNKNOWN',f'找不到罐 {pot}',404)
    receipt,reused=Dossier(bookshelf(),key).sign(pot,desk_pot,record['manifest'])
    return jsonify(receipt=receipt,reused=reused,desk=desk_payload(key))


@api.get('/receipts/<key>')
def receipts(key):
    return jsonify(key=key,receipts=dossier_for(key).view()['receipts'])


@api.get('/receipts/<key>/<rid>')
def one_receipt(key,rid):
    doc=dossier_for(key).receipt(rid)
    if doc is None:
        raise LedgerError('POT_UNKNOWN','找不到该分罐收据',404)
    return jsonify(doc)
