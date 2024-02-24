import asyncio
import hashlib
import logging
import time

from pytoniq_core.crypto.ciphers import Server
from pytoniq_core.crypto.signature import verify_sign

from .overlay import OverlayTransport
from .privacy import BroadcastCheckResult


class InvalidBroadcast(Exception):
    pass


class BroadcastSimple:
    """
    overlay.broadcast src:PublicKey certificate:overlay.Certificate flags:int data:bytes date:int signature:bytes = overlay.Broadcast;
    """

    def __init__(
            self,
            overlay_transport: OverlayTransport,
            data: dict,
    ):
        self._overlay = overlay_transport
        self._data = data
        self.is_valid = False
        self.data_bytes = self._overlay.schemas.serialize(self._data['data'].get('@type'), data['data'])
        """подумать нужна ли автоматическая десер простых бродкастов и вообще над байтами """
        self._logger = logging.getLogger(self.__class__.__name__)

    @classmethod
    def create(cls, overlay: OverlayTransport, data: bytes, flags: int = 0) -> "BroadcastSimple":
        ts = int(time.time())
        data_hash = hashlib.sha256(data).digest()
        to_sign_data = {
            'hash': cls.compute_broadcast_id(overlay, data_hash.hex(), overlay.client.get_key_id().hex(), flags),
            'date': ts
        }
        to_sign = overlay.schemas.serialize('overlay.broadcast.toSign', to_sign_data)
        signature = overlay.client.sign(to_sign)

        from_ = {'@type': 'pub.ed25519', 'key': overlay.client.ed25519_public.encode().hex()}
        broadcast = {
            '@type': 'overlay.broadcast',
            'src': from_,
            'certificate': {'@type': 'overlay.emptyCertificate'},
            'flags': flags,
            'data': data,
            'signature': signature,
            'date': ts
        }
        return cls(overlay, broadcast)

    @property
    def date(self) -> int:
        return self._data['date']

    @property
    def flags(self) -> int:
        return self._data['flags']

    @property
    def serialized(self) -> bytes:
        return self._overlay.schemas.serialize('overlay.broadcast', self._data)

    @property
    def hash(self) -> bytes:
        return hashlib.sha256(self.serialized).digest()

    @property
    def source_key(self) -> bytes:
        return bytes.fromhex(self._data['src']['key'])

    @property
    def broadcast_hash(self):
        data_hash = hashlib.sha256(self.data_bytes).digest()
        key_id = Server('', 0, self.source_key).get_key_id().hex()
        return self.compute_broadcast_id(self._overlay, data_hash.hex(), key_id, self.flags)

    @staticmethod
    def compute_broadcast_id(overlay: OverlayTransport, data_hash: str, src: str, flags: int) -> bytes:
        if flags & 1:
            src = (b'\x00' * 32).hex()
        broadcast_id_data = {'data_hash': data_hash, 'src': src, 'flags': flags}
        broadcast_id_serialized = overlay.schemas.serialize('overlay.broadcast.id', broadcast_id_data)
        return hashlib.sha256(broadcast_id_serialized).digest()

    def check_signature(self) -> bool:
        to_sign_data = {'hash': self.broadcast_hash.hex(),
                        'date': self.date}
        to_sign = self._overlay.schemas.serialize('overlay.broadcast.toSign', to_sign_data)
        return verify_sign(self.source_key, to_sign, self._data['signature'])

    def run_checks(self) -> None:
        if self.date < int(time.time()) - 20:
            raise InvalidBroadcast('broadcast is too old')

        if self.date > int(time.time()) + 20:
            raise InvalidBroadcast('broadcast is too new')

        if self.hash in self._overlay.broadcasts:
            raise InvalidBroadcast('broadcast already received')

        r = self._overlay.check_source_eligible(self.source_key, self._data['certificate'], len(self.data_bytes), False)

        if r == BroadcastCheckResult.Forbidden:
            raise InvalidBroadcast('source is not eligible')
        self.is_valid = r == BroadcastCheckResult.Allowed

        if not self.check_signature():
            raise InvalidBroadcast('invalid signature')

    async def run(self):
        try:
            self.run_checks()
        except InvalidBroadcast as e:
            self._logger.debug(f'Failed to check broadcast: {e}, brcst: {self._data}')
            return
        self._overlay.broadcasts[self.hash] = self
        source_key_id = Server('', 0, self.source_key).get_key_id()
        if not self.is_valid:
            if await self._overlay.check_broadcast(self._data['data'], source_key_id):
                self.is_valid = True
        if self.is_valid:
            await self._overlay.handle_broadcast(self._data['data'], source_key_id)
            await self.distribute()

    async def distribute(self) -> None:
        try:
            self.run_checks()
        except InvalidBroadcast as e:
            self._logger.debug(f'Failed to check broadcast: {e}, brcst: {self._data}')
            return
        self._overlay.broadcasts.add(self.hash)
        tasks = []
        peers = self._overlay.get_neighbours(3)
        for peer in peers:
            tasks.append(self._overlay.send_custom_message(self.serialized, peer))
        result = await asyncio.gather(*tasks, return_exceptions=True)
        failed = 0
        for r in result:
            if isinstance(r, Exception):
                failed += 1
        self._logger.debug(f'Spread broadcast: {failed} failed out of {len(result)}')
