import asyncio
import hashlib
import logging
import time

from pytoniq_core.crypto.ciphers import Server
from pytoniq_core.crypto.signature import verify_sign
from pytoniq_core.tl.generator import TlSchemas

from .overlay import OverlayTransport
from .privacy import BroadcastCheckResult
from ..rldp.raptorq import get_decoder, get_encoder


class InvalidBroadcastFec(Exception):
    pass


class BroadcastFec:

    def __init__(
            self,
            broadcast_hash: bytes,
            src: bytes,
            data_hash: bytes,
            flags: int,
            date: int,
            fec_type: dict,
            overlay: OverlayTransport
    ):
        self.broadcast_hash = broadcast_hash
        self.src = src
        self.data_hash = data_hash
        self.flags = flags
        self.date = date
        self.fec_type = fec_type
        self.decoder = None
        self.encode = None
        self.next_seqno = 0
        self.received_parts = 0
        self.parts = {}
        self.result = None
        self.ready = False
        self.completed_neighbours = set()
        self._overlay = overlay
        self._logger = logging.getLogger(self.__class__.__name__)

        self.run_checks()
        self.init_fec_type()

    def run_checks(self):
        if self.fec_type['data_size'] > self._overlay.max_fec_broadcast_size:
            raise InvalidBroadcastFec('too big fec broadcast')

    def init_fec_type(self):
        if self.fec_type['@type'] != 'fec.raptorQ':
            raise InvalidBroadcastFec('unsupported fec type')
        self.decoder = get_decoder(
            self._overlay.raptorq_engine,
            self.fec_type['data_size'],
            self.fec_type['symbol_size'],
            self.fec_type['symbols_count']
        )

    def received_part(self, seqno: int) -> bool:
        if seqno + 64 < self.next_seqno:
            return True
        if seqno >= self.next_seqno:
            return False
        return bool(self.received_parts & (1 << (self.next_seqno - seqno - 1)))

    def add_received_part(self, seqno: int):
        if seqno < self.next_seqno:
            self.received_parts |= (1 << (self.next_seqno - seqno - 1))
        else:
            old = self.next_seqno
            self.next_seqno = seqno + 1
            if self.next_seqno - old >= 64:
                self.received_parts = 1
            else:
                self.received_parts = self.received_parts << (self.next_seqno - old)
                self.received_parts |= 1

    def is_eligible_sender(self, src: bytes):
        if self.flags & 1:
            return True
        return src == self.src

    def add_part(self, seqno: int, data: bytes, serialized: bytes) -> bool:
        res = self.decoder.add_symbol(seqno, data)
        self.parts[seqno] = serialized
        return res

    def finish(self):
        if not self.decoder.may_try_decode():
            raise Exception('need more parts')
        result = self.decoder.try_decode()
        if result:
            if hashlib.sha256(result).digest() != self.data_hash:
                raise InvalidBroadcastFec('data hash mismatch')
            # self.encoder = get_encoder(self.result, self.fec_type['symbol_size'])  todo
            self.ready = True
            del self.decoder  # can be useful: so we dont need to wait for gc
            self.decoder = None
        return result

    def finalized(self):
        return self.ready

    def add_completed(self, peer_id: bytes):
        self.completed_neighbours.add(peer_id)

    async def distribute_part(self, seqno: int):
        if seqno not in self.parts:
            return
        data = self.parts.get(seqno)
        peers = self._overlay.get_neighbours(5)
        tasks = []
        for peer in peers:
            if peer.get_key_id() in self.completed_neighbours:  # todo: short broadcasts
                continue
            tasks.append(self._overlay.send_custom_message(data, peer))
        result = await asyncio.gather(*tasks, return_exceptions=True)


class BroadcastFecPart:
    """
    overlay.broadcastFec src:PublicKey certificate:overlay.Certificate data_hash:int256 data_size:int flags:int
                         data:bytes seqno:int fec:fec.Type date:int signature:bytes = overlay.Broadcast;
    """

    def __init__(
            self,
            overlay_transport: OverlayTransport,
            data: dict
    ):
        self.brcst: BroadcastFec = None
        self._overlay = overlay_transport
        self._data = data
        self.untrusted = False

        self._logger = logging.getLogger(self.__class__.__name__)

    @property
    def date(self) -> int:
        return self._data['date']

    @property
    def flags(self) -> int:
        return self._data['flags']

    @property
    def seqno(self) -> int:
        return self._data['seqno']

    @property
    def source_key(self) -> bytes:
        return bytes.fromhex(self._data['src']['key'])

    @property
    def broadcast_hash(self):
        key_id = Server('', 0, self.source_key).get_key_id().hex()
        return self.compute_broadcast_id(self._overlay, self._data['data_hash'], key_id, self._data['flags'], self._data['fec'], self._data['data_size'])

    @property
    def part_data_hash(self):
        return hashlib.sha256(self._data['data']).digest()

    @property
    def part_hash(self):
        return self.compute_broadcast_part_id(self._overlay.schemas, self.broadcast_hash.hex(), self.part_data_hash.hex(), self.seqno)

    @property
    def serialized(self) -> bytes:
        return self._overlay.schemas.serialize('overlay.broadcastFec', self._data)

    @property
    def is_short(self) -> bool:
        return 'Short' in self._data['@type']

    @staticmethod
    def compute_broadcast_id(overlay: OverlayTransport, data_hash: str, src: str, flags: int, fec_type: dict, size: int) -> bytes:
        """
        overlay.broadcastFec.id src:int256 type:int256 data_hash:int256 size:int flags:int = overlay.broadcastFec.Id;
        """
        if flags & 1:
            src = (b'\x00' * 32).hex()
        type_ = hashlib.sha256(overlay.schemas.serialize(fec_type['@type'], fec_type)).digest().hex()
        broadcast_id_data = {'data_hash': data_hash, 'src': src, 'flags': flags, 'type': type_, 'size': size}
        broadcast_id_serialized = overlay.schemas.serialize('overlay.broadcastFec.id', broadcast_id_data)
        return hashlib.sha256(broadcast_id_serialized).digest()

    @staticmethod
    def compute_broadcast_part_id(schemes: TlSchemas, broadcast_hash: str, data_hash: str, seqno: int):
        """
        overlay.broadcastFec.partId broadcast_hash:int256 data_hash:int256 seqno:int = overlay.broadcastFec.PartId;
        """
        data = {'broadcast_hash': broadcast_hash, 'data_hash': data_hash, 'seqno': seqno}
        return hashlib.sha256(schemes.serialize('overlay.broadcastFec.partId', data)).digest()

    def check_signature(self) -> bool:
        to_sign_data = {'hash': self.part_hash.hex(),
                        'date': self.date}
        to_sign = self._overlay.schemas.serialize('overlay.broadcast.toSign', to_sign_data)
        return verify_sign(self.source_key, to_sign, self._data['signature'])

    def run_checks(self):
        if self.date < int(time.time()) - 20:
            raise InvalidBroadcastFec('broadcast is too old')

        if self.date > int(time.time()) + 20:
            raise InvalidBroadcastFec('broadcast is too new')

        if self._data['fec']['@type'] != 'fec.raptorQ':
            raise InvalidBroadcastFec('unsupported fec type')

        if self.brcst and self.brcst.received_part(self.seqno):
            raise InvalidBroadcastFec('broadcast already received')

        r = self._overlay.check_source_eligible(self.source_key, self._data['certificate'], self._data['data_size'], True)
        if r == BroadcastCheckResult.Forbidden:
            raise InvalidBroadcastFec('source is not eligible')
        if r == BroadcastCheckResult.NeedCheck:
            self.untrusted = True

        if self.brcst:
            if not self.brcst.is_eligible_sender(self.source_key):
                raise InvalidBroadcastFec('source is not eligible')

        if not self.check_signature():
            raise InvalidBroadcastFec('signature is not valid')

    async def apply(self):
        if not self.brcst:
            self.brcst = self._overlay.fec_broadcasts.get(self.broadcast_hash)
        if not self.brcst:
            if self.is_short:
                self._logger.debug(f'short broadcast part for incomplete broadcast')
                return
            b = BroadcastFec(self.broadcast_hash, self.source_key, bytes.fromhex(self._data['data_hash']),
                             self._data['flags'], self.date, self._data['fec'], self._overlay)
            self.brcst = b
            self._overlay.fec_broadcasts[self.broadcast_hash] = b
        if self.brcst.received_part(self.seqno):
            raise InvalidBroadcastFec('duplicate part')
        self.brcst.add_received_part(self.seqno)

        if self.brcst.finalized() and self.is_short:
            raise InvalidBroadcastFec('short broadcast part for incomplete broadcast')

        if not self.brcst.finalized():
            self.brcst.add_part(
                self.seqno,
                self._data['data'],
                self._overlay.schemas.serialize(self._data['@type'], self._data)
            )
            if self.brcst.decoder.may_try_decode():
                try:
                    r = self.brcst.finish()
                except InvalidBroadcastFec:
                    self._logger.debug(f'failed to finish broadcast: {self._data}')
                    return
                except Exception as e:
                    if 'need more parts' in str(e):
                        return
                    raise e

                try:
                    r, _ = self._overlay.schemas.deserialize(r)
                except:
                    pass

                if self.untrusted:
                    if await self._overlay.check_broadcast(r, self.source_key):
                        await self._overlay.handle_broadcast(r, self.source_key)
                        # await self.distribute()  # todo: check why we distribute only one part
                else:
                    await self._overlay.handle_broadcast(r, self.source_key)

    async def run(self):
        try:
            self.run_checks()
        except InvalidBroadcastFec as e:
            self._logger.debug(f'Failed to check broadcast: {e}, brcst: {self._data}')
            return
        try:
            await self.apply()
        except InvalidBroadcastFec as e:
            self._logger.debug(f'Failed to apply broadcast: {e}, brcst: {self._data}')
            return
        # if not self.untrusted:
        await self.distribute()

    async def distribute(self):
        await self.brcst.distribute_part(self.seqno)

    @classmethod
    def create(
            cls, overlay: OverlayTransport, part: bytes, data_hash: str,
            seqno: int, flags: int, fec_type: dict, data_size: int, date: int
    ):
        broadcast_hash = cls.compute_broadcast_id(
            overlay=overlay,
            data_hash=data_hash,
            src=overlay.client.get_key_id().hex(),
            flags=flags,
            fec_type=fec_type,
            size=data_size
        )
        part_data_hash = hashlib.sha256(part).digest()
        part_hash = cls.compute_broadcast_part_id(overlay.schemas, broadcast_hash.hex(), part_data_hash.hex(), seqno)

        to_sign_data = {'hash': part_hash.hex(),
                        'date': date}
        to_sign = overlay.schemas.serialize('overlay.broadcast.toSign', to_sign_data)
        signature = overlay.client.sign(to_sign)

        part_data = {
            '@type': 'overlay.broadcastFec',
            'src': {'@type': 'pub.ed25519', 'key': overlay.client.ed25519_public.encode().hex()},
            'certificate': overlay.get_certificate(),  # todo certificates
            'data_hash': data_hash,
            'data_size': data_size,
            'flags': flags,
            'data': part,
            'seqno': seqno,
            'fec': fec_type,
            'date': date,
            'signature': signature
        }
        return cls(overlay, part_data)


async def create_fec_broadcast(overlay: OverlayTransport, data: bytes, flags: int):
    if len(data) > 1 << 27:
        raise InvalidBroadcastFec('too big data')

    symbol_size = overlay.max_simple_broadcast_size
    to_send = int((len(data) / symbol_size + 1) * 2)
    symbols_count = (len(data) + symbol_size - 1) // symbol_size

    data_hash = hashlib.sha256(data).digest()
    ts = int(time.time())
    fec_type = {'@type': 'fec.raptorQ', 'data_size': len(data), 'symbol_size': symbol_size, 'symbols_count': symbols_count}
    try:
        encoder = get_encoder(
            overlay.raptorq_engine,
            data,
            symbol_size
        )
    except:
        raise InvalidBroadcastFec('failed to create encoder')

    seqno = 0
    broadcast_hash = b''

    while seqno < to_send:
        for _ in range(4):
            part = encoder.gen_symbol(seqno)
            if part is None:
                seqno += 1
                continue
            part = BroadcastFecPart.create(overlay, part, data_hash.hex(), seqno, flags, fec_type, len(data), ts)
            try:
                await part.run()
            except Exception as e:
                logging.getLogger('create_fec_broadcast').debug(f'failed to run part: {e}')
                pass
            broadcast_hash = part.broadcast_hash

            seqno += 1
        await asyncio.sleep(0.01)

    return broadcast_hash
