import asyncio
import time
import hashlib
import typing

from pytoniq_core.tl.generator import TlGenerator

from pytoniq_core import BlockIdExt, Block, Slice
from pytoniq_core.crypto.ciphers import get_random

from .adnl import Node, AdnlTransport, AdnlTransportError


class OverlayTransportError(AdnlTransportError):
    pass


class OverlayNode(Node):

    def __init__(
            self,
            peer_host: str,  # ipv4 host
            peer_port: int,  # port
            peer_pub_key: str,
            transport: "OverlayTransport"
    ):
        self.transport: "OverlayTransport" = None
        super().__init__(peer_host, peer_port, peer_pub_key, transport)

    async def send_ping(self) -> None:
        peers = [
            self.transport.get_signed_myself()
        ]
        await self.transport.send_query_message('overlay.getRandomPeers', {'peers': {'nodes': peers}}, peer=self)


class OverlayTransport(AdnlTransport):

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
    def get_mainnet_overlay_id(cls, workchain: int = 0, shard: int = -9223372036854775808) -> str:
        return cls.get_overlay_id('5e994fcf4d425c0a6ce6a792594b7173205f740a39cd56f537defd28b48a0f6e', workchain, shard)

    @classmethod
    def get_testnet_overlay_id(cls, workchain: int = 0, shard: int = -9223372036854775808) -> str:
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
            if data[0]['@type'] == 'overlay.query':
                assert data[0]['overlay'] == self.overlay_id, 'Unknown overlay id received'
            data = data[-1]
        if 'broadcast' in data['@type']:
            # Force broadcast spreading for the network stability. Can be removed in the future.
            # Note that this is almost takes no time to do and will be done in the background.
            asyncio.create_task(self._spread_broadcast(message, ignore_errors=True))

        await self._process_custom_message_handler(data, peer)

    async def _spread_broadcast(self, message: dict, ignore_errors: bool = True):
        tasks = []
        for _, peer in self.peers.items():
            tasks.append(self.send_custom_message(message, peer))
        result = await asyncio.gather(*tasks, return_exceptions=ignore_errors)
        failed = 0
        for r in result:
            if isinstance(r, Exception):
                failed += 1
        self.logger.debug(f'Spread broadcast: {failed} failed out of {len(result)}')

    def get_signed_myself(self):
        ts = int(time.time())

        overlay_node_data = {'id': {'@type': 'pub.ed25519', 'key': self.client.ed25519_public.encode().hex()},
                             'overlay': self.overlay_id, 'version': ts, 'signature': b''}

        overlay_node_to_sign = self.schemas.serialize(self.schemas.get_by_name('overlay.node.toSign'),
                                                      {'id': {'id': self.client.get_key_id().hex()},
                                                       'overlay': self.overlay_id,
                                                       'version': overlay_node_data['version']})
        signature = self.client.sign(overlay_node_to_sign)

        overlay_node = overlay_node_data | {'signature': signature}
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

    def get_message_with_overlay_prefix(self, schema_name: str, data: dict) -> bytes:
        return (self.schemas.serialize(
                    schema=self.schemas.get_by_name('overlay.query'),
                    data={'overlay': self.overlay_id})
                + self.schemas.serialize(
                    schema=self.schemas.get_by_name(schema_name),
                    data=data)
                )

    def _get_default_message(self):
        peers = [
            self.get_signed_myself()
        ]
        return {
            '@type': 'adnl.message.query',
            'query_id': get_random(32),
            'query': self.get_message_with_overlay_prefix('overlay.getRandomPeers', {'peers': {'nodes': peers}})
        }

    async def get_random_peers(self, peer: OverlayNode):
        overlay_node = self.get_signed_myself()

        peers = [
            overlay_node
        ]
        return await self.send_query_message(tl_schema_name='overlay.getRandomPeers', data={'peers': {'nodes': peers}},
                                             peer=peer)

    async def get_capabilities(self, peer: OverlayNode):
        return await self.send_query_message(tl_schema_name='tonNode.getCapabilities', data={}, peer=peer)
