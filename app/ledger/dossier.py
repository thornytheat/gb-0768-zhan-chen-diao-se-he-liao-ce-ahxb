import fcntl
import json
import os
import threading
from contextlib import contextmanager
from datetime import UTC, datetime
from hashlib import sha256
from tempfile import NamedTemporaryFile

from app.faults import LedgerError
from app.ledger.identity import encoded
from app.settings import EDITION

DECISIONS = ('confirm', 'reject')
TERMINAL = {'confirm': 'CONFIRMED', 'reject': 'REJECTED'}


def receipt_id(key, pot):
    """同一留档同一罐的签发收据编号确定不变，重试不会另出一份。"""
    return sha256(encoded({'key': key, 'pot': pot, 'kind': 'pot-receipt'})).hexdigest()[:16]


class Dossier:
    """一份工单留档对应的复核与签发状态，文件锁覆盖线程与多进程并发。"""

    def __init__(self, shelf, key):
        self.shelf = shelf
        self.key = key
        self.state_path = shelf.directory / f'{key}.dossier'
        self.lock_path = shelf.directory / f'{key}.lock'
        self._thread_lock = threading.Lock()

    @contextmanager
    def _locked(self):
        with self._thread_lock:
            self.lock_path.touch(exist_ok=True)
            with open(self.lock_path, 'r') as handle:
                fcntl.flock(handle, fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(handle, fcntl.LOCK_UN)

    def _read(self):
        try:
            return json.loads(self.state_path.read_bytes())
        except FileNotFoundError:
            return {'decisions': {}, 'receipts': {}}

    def _write(self, state):
        with NamedTemporaryFile(dir=self.shelf.directory, prefix='.dossier-', delete=False) as temp:
            temp.write(encoded(state))
            temp.flush()
            os.fsync(temp.fileno())
            draft=temp.name
        os.replace(draft, self.state_path)

    def view(self):
        with self._locked():
            state = self._read()
            return {'decisions': dict(state['decisions']),
                    'receipts': [dict(item) for item in state['receipts'].values()]}

    def review(self, pot, decision):
        if decision not in DECISIONS:
            raise LedgerError('REVIEW_INVALID', '复核结论需为 confirm 或 reject', 400)
        with self._locked():
            state = self._read()
            prior = state['decisions'].get(pot)
            now = datetime.now(UTC).isoformat(timespec='seconds')
            if prior is not None:
                if prior['decision'] == decision:
                    return prior, True
                raise LedgerError('REVIEW_CONFLICT',
                                  f'罐 {pot} 已有相反结论：{prior["decision"]}', 409)
            entry = {'pot': pot, 'decision': decision, 'status': TERMINAL[decision],
                     'decided_at': now, 'edition': EDITION}
            state['decisions'][pot] = entry
            self._write(state)
            return entry, False

    def sign(self, pot, desk_pot, manifest):
        with self._locked():
            state = self._read()
            existing = state['receipts'].get(pot)
            if existing is not None:
                return existing, True
            decision = state['decisions'].get(pot)
            if decision is not None and decision['decision'] == 'reject':
                raise LedgerError('POT_REJECTED', f'罐 {pot} 复核已驳回，不得签发', 422)
            if desk_pot['status'] == 'HELD' and decision is None:
                raise LedgerError('POT_HELD', f'罐 {pot} 仍挂起，复核确认后才能签发', 422)
            rid = receipt_id(self.key, pot)
            doc = {
                'receipt_id': rid, 'key': self.key, 'order': manifest['order'],
                'pot': pot, 'document': '调色分罐收据',
                'basis': 'review_confirmed' if decision is not None else 'uncontested',
                'issued_at': datetime.now(UTC).isoformat(timespec='seconds'),
                'edition': EDITION,
                'lot_lines': desk_pot['lot_lines'], 'totals': desk_pot['totals'],
                'sha256': '',
            }
            doc['sha256'] = sha256(encoded({k: v for k, v in doc.items() if k != 'sha256'})).hexdigest()
            state['receipts'][pot] = doc
            self._write(state)
            return doc, False

    def receipt(self, rid):
        with self._locked():
            state = self._read()
            return next((doc for doc in state['receipts'].values() if doc['receipt_id'] == rid), None)
