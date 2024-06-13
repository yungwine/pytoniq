import enum
import inspect
import random
import time
import hashlib
import typing

from pytoniq_core.tl.generator import TlGenerator
from pytoniq_core.crypto.ciphers import get_random, Server

from ..adnl import Node, AdnlTransport, AdnlTransportError
from .privacy import OverlayPrivacyRules, Certificate, BroadcastCheckResult


class OverlayTransportError(AdnlTransportError):
    pass


class OverlayNode(Node):

    PING_INTERVAL = 10

    def __init__(
            self,
            peer_host: str,  # ipv4 host
            peer_port: int,  # port
            peer_pub_key: str,
            transport: "OverlayTransport"
    ):
        self.transport: "OverlayTransport" = None
        self.signature = b''
        self.version = 0
        super().__init__(peer_host, peer_port, peer_pub_key, transport)

    def add_params(self, signature: bytes, version: int):
        self.signature = signature
        self.version = version

    def to_tl(self) -> typing.Optional[dict]:
        if not self.signature:
            return None
        return {
            '@type': 'overlay.node',
            'id': {'@type': 'pub.ed25519', 'key': self.ed25519_public.encode().hex()},
            'overlay': self.transport.overlay_id,
            'version': self.version,
            'signature': self.signature
        }

    async def send_ping(self) -> None:
        peers = [
            self.transport.get_signed_myself()
        ]
        await self.transport.send_query_message('overlay.getRandomPeers', {'peers': {'nodes': peers}}, peer=self)


class OverlayTransport(AdnlTransport):
    max_simple_broadcast_size = 768
    max_fec_broadcast_size = 16 << 20

    def __init__(self,
                 private_key: bytes = None,
                 tl_schemas_path: str = None,
                 local_address: tuple = ('0.0.0.0', None),
                 overlay_id: typing.Union[str, bytes] = None,
                 *args, **kwargs
                 ) -> None:

        super().__init__(private_key, tl_schemas_path, local_address, *args, **kwargs)
        if overlay_id is None:
            raise OverlayTransportError('must provide overlay id in OverlayTransport')

        if isinstance(overlay_id, bytes):
            overlay_id = overlay_id.hex()

        self.overlay_id = overlay_id
        self.broadcasts = {}
        self.fec_broadcasts = {}
        self.broadcast_checkers: typing.Dict[str, typing.Callable] = {}
        self.broadcast_handlers: typing.Dict[str, typing.Callable] = {}
        if 'rules' in kwargs:
            self.rules = kwargs['rules']
            assert isinstance(self.rules, OverlayPrivacyRules), 'rules must be instance of OverlayPrivacyRules'
        else:
            self.rules = OverlayPrivacyRules.default(allow_fec=kwargs.get('allow_fec', False))
        if self.rules.allow_fec:
            self.raptorq_engine = kwargs.get('raptorq_engine', None)
        self.max_peers = kwargs.get('max_peers', 30)
        self.signed_myself = self.get_signed_myself()

    @staticmethod
    def get_overlay_id(zero_state_file_hash: typing.Union[bytes, str],
                       workchain: int = 0, shard: int = -9223372036854775808) -> str:

        if isinstance(zero_state_file_hash, bytes):
            zero_state_file_hash = zero_state_file_hash.hex()

        schemes = TlGenerator.with_default_schemas().generate()

        sch = schemes.get_by_name('tonNode.shardPublicOverlayId')
        data = {
            "workchain": workchain,
            "shard": shard,
            "zero_state_file_hash": zero_state_file_hash
        }

        key_id = hashlib.sha256(schemes.serialize(sch, data)).digest()

        sch = schemes.get_by_name('pub.overlay')
        data = {
            'name': key_id
        }

        key_id = schemes.serialize(sch, data)

        return hashlib.sha256(key_id).digest().hex()

    @classmethod
    def get_mainnet_overlay_id(cls, workchain: int = 0, shard: int = -1 << 63) -> str:
        return cls.get_overlay_id('5e994fcf4d425c0a6ce6a792594b7173205f740a39cd56f537defd28b48a0f6e', workchain, shard)

    @classmethod
    def get_testnet_overlay_id(cls, workchain: int = 0, shard: int = -1 << 63) -> str:
        return cls.get_overlay_id('67e20ac184b9e039a62667acc3f9c00f90f359a76738233379efa47604980ce8', workchain, shard)

    async def _process_query_message(self, message: dict, peer: OverlayNode):
        query = message.get('query')
        if isinstance(query, list):
            if query[0]['@type'] == 'overlay.query':
                assert query[0]['overlay'] == self.overlay_id, 'Unknown overlay id received'
            query = query[-1]
        await self._process_query_handler(message, query, peer)

    async def _process_custom_message(self, message: dict, peer: Node):
        data = message.get('data')
        if isinstance(data, list):
            if data[0]['@type'] in ('overlay.query', 'overlay.message'):
                assert data[0]['overlay'] == self.overlay_id, 'Unknown overlay id received'
            data = data[-1]
        # Force broadcast distributing: Note that this is almost takes no time and will be done in the background
        if data['@type'] == 'overlay.broadcast':
            from .broadcast import BroadcastSimple
            try:
                await BroadcastSimple(self, data).run()
            except Exception as e:
                self.logger.debug(f'Error while processing broadcast: {type(e)}: {e}')
                return
            self.bcast_gc()
            return
        if data['@type'] == 'overlay.broadcastFec':
            from .fec_broadcast import BroadcastFecPart
            try:
                await BroadcastFecPart(self, data).run()
            except Exception as e:
                self.logger.debug(f'Error while processing broadcastFec: {type(e)}: {e}')
            self.bcast_gc()
            return

        await self._process_custom_message_handler(data, peer)

    def get_neighbours(self, max_size: int):
        if len(self.peers) <= max_size:
            return list(self.peers.values())
        peers = random.choices(list(self.peers.values()), k=max_size)  # https://github.com/ton-blockchain/ton/blob/e30049930a7372a3c1d28a1e59956af8eb489439/overlay/overlay-broadcast.cpp#L69
        return peers

    def get_signed_myself(self):
        ts = int(time.time())
        if self.signed_myself['version'] > ts - 60:
            return self.signed_myself

        overlay_node_data = {'id': {'@type': 'pub.ed25519', 'key': self.client.ed25519_public.encode().hex()},
                             'overlay': self.overlay_id, 'version': ts, 'signature': b''}

        overlay_node_to_sign = self.schemas.serialize(self.schemas.get_by_name('overlay.node.toSign'),
                                                      {'id': {'id': self.local_id.hex()},
                                                       'overlay': self.overlay_id,
                                                       'version': overlay_node_data['version']})
        signature = self.client.sign(overlay_node_to_sign)

        overlay_node = overlay_node_data | {'signature': signature}
        self.signed_myself = overlay_node
        return overlay_node

    async def send_query_message(self, tl_schema_name: str, data: dict, peer: Node) -> typing.List[typing.Union[dict, bytes]]:
        """
        :param tl_schema_name:
        :param data:
        :param peer:
        :return: dict if response was known TL schema, bytes otherwise
        """

        message = {
            '@type': 'adnl.message.query',
            'query_id': get_random(32),
            'query': self.schemas.serialize(self.schemas.get_by_name('overlay.query'), data={'overlay': self.overlay_id})
                     + self.schemas.serialize(self.schemas.get_by_name(tl_schema_name), data)
        }
        data = {
            'message': message,
        }

        result = await self.send_message_in_channel(data, None, peer)
        return result

    async def send_custom_message(self, message: typing.Union[dict, bytes], peer: Node) -> list:
        if isinstance(message, dict):
            message = self.schemas.serialize(message['@type'], message)

        custom_message = {
            '@type': 'adnl.message.custom',
            'data': self.get_message_with_overlay_prefix(message, False)
        }

        data = {
            'message': custom_message,
        }

        result = await self.send_message_in_channel(data, None, peer)
        return result

    def get_message_with_overlay_prefix(self, data: dict, query: bool) -> bytes:
        if isinstance(data, dict):
            data = self.schemas.serialize(schema=data['@type'], data=data)
        return (self.schemas.serialize(
                    schema='overlay.query' if query else 'overlay.message',
                    data={'overlay': self.overlay_id}) + data
                )

    def _get_default_message(self):
        peers = [
            self.get_signed_myself()
        ]
        return {
            '@type': 'adnl.message.query',
            'query_id': get_random(32),
            'query': self.get_message_with_overlay_prefix(
                {'@type': 'overlay.getRandomPeers', 'peers': {'nodes': peers}},
                True
            )
        }

    async def get_random_peers(self, peer: OverlayNode):
        known_peers = self.get_neighbours(5)
        peers = [self.get_signed_myself()]
        for peer in known_peers:
            if peer.to_tl():
                peers.append(peer.to_tl())
        return await self.send_query_message(tl_schema_name='overlay.getRandomPeers', data={'peers': {'nodes': peers}},
                                             peer=peer)

    async def get_capabilities(self, peer: OverlayNode):
        return await self.send_query_message(tl_schema_name='tonNode.getCapabilities', data={}, peer=peer)

    def bcast_gc(self):
        i = iter(self.broadcasts.copy())
        while len(self.broadcasts) > 250:
            brcst = next(i)
            del self.broadcasts[brcst]
        for b_hash, b in list(self.fec_broadcasts.items()):
            if b.date < time.time() - 60:
                del self.fec_broadcasts[b_hash]
            else:
                break

    def check_source_eligible(self, source: bytes, cert: dict, size: int, is_feq: bool) -> BroadcastCheckResult:
        if size == 0:
            return BroadcastCheckResult.Forbidden
        key_id = Server('', 0, source).get_key_id()
        r = self.rules.check_rules(key_id, size, is_feq)
        if cert['@type'] == 'overlay.emptyCertificate' or r == BroadcastCheckResult.Allowed:
            return r
        r2 = Certificate(cert, self.schemas).check(key_id, bytes.fromhex(self.overlay_id), size, is_feq)
        issuer_key_id = Server('', 0, bytes.fromhex(cert['issued_by']['key'])).get_key_id()
        r2 = min(r2.value, self.rules.check_rules(issuer_key_id, size, is_feq).value)
        return BroadcastCheckResult(max(r.value, r2))

    async def check_broadcast(self, data: typing.Union[bytes, dict], src_key_id: bytes) -> bool:
        if isinstance(data, dict):
            checker = self.broadcast_checkers.get(data['@type'], self.broadcast_checkers.get(None))
        else:
            checker = self.broadcast_checkers.get(None)
        if checker:
            if inspect.iscoroutinefunction(checker):
                try:
                    return await checker(data, src_key_id)
                except:
                    return False
            try:
                return checker(data, src_key_id)
            except:
                return False
        return True

    async def handle_broadcast(self, data: typing.Union[bytes, dict], src_key_id: bytes):
        if isinstance(data, dict):
            handler = self.broadcast_handlers.get(data['@type'], self.broadcast_handlers.get(None))
        else:
            handler = self.broadcast_handlers.get(None)
        if handler:
            if inspect.iscoroutinefunction(handler):
                try:
                    return await handler(data, src_key_id)
                except:
                    return False
            try:
                return handler(data, src_key_id)
            except:
                return False
        return True

    def set_broadcast_checker(self, type_: str, checker: typing.Callable):
        """
        :param type_: TL type of broadcast
        :param checker: function to handle message. **Must** return dict or bytes or None. If
            None returned than answer won't be sent to the sender. Takes two arguments: data (dict or bytes) and src_key_id (bytes)
        :return:
        """
        self.broadcast_checkers[type_] = checker

    def set_default_broadcast_checker(self, checker: typing.Callable):
        self.set_broadcast_checker(None, checker)

    def set_broadcast_handler(self, type_: str, handler: typing.Callable):
        """
        :param type_: TL type of broadcast
        :param handler: function to handle message. **Must** return dict or bytes or None. If
            None returned than answer won't be sent to the sender. Takes two arguments: data (dict or bytes) and src_key_id (bytes)
        :return:
        """
        self.broadcast_handlers[type_] = handler

    def set_default_broadcast_handler(self, handler: typing.Callable):
        self.set_broadcast_handler(None, handler)

    def get_certificate(self):
        data = {'@type': 'overlay.certificate', 'issued_by': {'@type': 'pub.ed25519', 'key': self.client.ed25519_public.encode().hex()},
                'expire_at': int(time.time()) + 3600, 'max_size': 16 << 20, 'signature': b''}
        to_sign = self.schemas.serialize('overlay.certificate', data)
        signature = self.client.sign(to_sign)
        data['signature'] = signature
        return data
