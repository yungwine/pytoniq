import asyncio.exceptions
import base64
import time
import typing
import hashlib
import socket
import struct

import requests
from pytoniq_core.crypto.ciphers import Client, Server
from pytoniq_core.crypto.signature import verify_sign
from pytoniq_core.tl import TlGenerator

from .adnl import Node, AdnlTransport
from .overlay import OverlayNode, OverlayTransport


class DhtError(Exception):
    pass


class DhtValueNotFoundError(DhtError):
    pass


class DhtNode(Node):

    async def find_value(self, key: bytes, k: int = 6):
        data = {'key': key.hex(), 'k': k}
        return await self.transport.send_query_message('dht.findValue', data, self)

    async def store_value(self, value: dict):
        data = {'value': value}
        return await self.transport.send_query_message('dht.store', data, self)

    @classmethod
    def from_dict(cls, transport: AdnlTransport, data: dict, check_signature=True) -> "DhtNode":
        try:
            pub_k = bytes.fromhex(data['id']['key'])
            pub_k_b64 = base64.b64encode(pub_k)
        except ValueError:
            pub_k_b64 = data['id']['key']
            pub_k = base64.b64decode(pub_k_b64)
            data['id']['key'] = pub_k.hex()
        if isinstance(data['signature'], bytes):
            signature = data['signature']
        else:
            signature = base64.b64decode(data['signature'])
        data['signature'] = b''

        # check signature
        if check_signature:
            schemas = TlGenerator.with_default_schemas().generate()
            signed_message = schemas.serialize(schema=schemas.get_by_name('dht.node'), data=data)
            if not verify_sign(pub_k, signed_message, signature):
                raise Exception('invalid node signature!')

        node_addr = data['addr_list']['addrs'][0]
        host = socket.inet_ntoa(struct.pack('>i', node_addr['ip']))
        return cls(peer_host=host, peer_port=node_addr['port'], peer_pub_key=pub_k_b64, transport=transport)


class DhtClient:

    def __init__(self,
                 nodes: typing.List[DhtNode],
                 adnl_transport: AdnlTransport,
                 tl_schemas_path: typing.Optional[str] = None
                 ):
        self.adnl_transport: AdnlTransport = adnl_transport
        self.nodes_set: set = set(nodes)
        assert len(nodes) >= 1, 'expected at least 1 node in the list'
        if tl_schemas_path is None:
            self.schemas = TlGenerator.with_default_schemas().generate()
        else:
            self.schemas = TlGenerator(tl_schemas_path).generate()

    async def close(self):
        """
        disconnects to all known nodes
        :return:
        """
        for node in self.nodes_set:
            await node.disconnect()

    def get_dht_key_id_tl(self, id_: typing.Union[bytes, str], name: bytes = b'address', idx: int = 0):
        if isinstance(id_, str):
            id_ = bytes.fromhex(id_)
        dht_key_sch = self.schemas.get_by_name('dht.key')
        serialized = self.schemas.serialize(dht_key_sch, data={'id': id_.hex(), 'name': name, 'idx': idx})
        return hashlib.sha256(serialized).digest()

    @staticmethod
    def get_dht_key_id(id_: typing.Union[bytes, str], name: bytes = b'address', idx: int = 0):
        """
        Same as the method above but without using TlGenerator
        """
        if isinstance(id_, str):
            id_ = bytes.fromhex(id_)
        to_hash = b'\x8f\xdeg\xf6' + id_ + len(name).to_bytes(1, 'big') + name + idx.to_bytes(4, 'little')
        return hashlib.sha256(to_hash).digest()

    @staticmethod
    def find_distance_between_nodes(key_id_1: typing.Union[bytes, int], key_id_2: typing.Union[bytes, int]):
        if isinstance(key_id_1, bytes):
            key_id_1 = int.from_bytes(key_id_1, 'big')
        if isinstance(key_id_2, bytes):
            key_id_2 = int.from_bytes(key_id_2, 'big')
        return key_id_1 ^ key_id_2

    @classmethod
    def build_priority_list(cls, nodes: typing.Iterable, key_id: bytes) -> typing.List[DhtNode]:
        return sorted(nodes, key=lambda i: cls.find_distance_between_nodes(i.key_id, key_id))

    async def find_value(self, key: bytes, k: int = 6, timeout: int = 10):
        start_time = time.time()
        while True:
            if time.time() - start_time > timeout:  # TODO improve timeout
                raise asyncio.exceptions.TimeoutError()
            nodes = self.build_priority_list(self.nodes_set, key)

            for node in nodes:
                if not node.connected:
                    try:
                        await asyncio.wait_for(node.connect(), 1)
                    except asyncio.TimeoutError:
                        continue
                try:
                    resp = await node.find_value(key=key, k=k)
                except asyncio.exceptions.TimeoutError:
                    continue
                except Exception as e:
                    raise e  # ?

                resp = resp[0]
                if resp['@type'] == 'dht.valueNotFound':
                    new_nodes = resp['nodes']['nodes']
                    new_nodes_set = set()
                    for n in new_nodes:
                        new_nodes_set.add(DhtNode.from_dict(self.adnl_transport, n, True))
                    old_nodes = self.nodes_set.copy()
                    self.nodes_set = self.nodes_set.union(new_nodes_set)
                    if self.nodes_set == old_nodes:
                        raise DhtValueNotFoundError(f'value {key.hex()} not found')
                    break
                elif resp['@type'] == 'dht.valueFound':
                    return resp
                else:
                    raise DhtError(f'received unknown response type: {resp}')

    async def raw_store_value(self, dht_value: dict, try_find_after: bool = True):
        """
        dht.store value:dht.value = dht.Stored;

        :param dht_value: dict that represents `dht.value` TL scheme
        :param try_find_after: tries to find value in known peers after storage
        :return: bool was value stored or not
        """
        s = time.time()
        key = dht_value.get('key', {}).get('key', {})
        if key is None:
            raise DhtError(f'must provide dht.value dict to the method')
        key_id = self.get_dht_key_id(bytes.fromhex(key.get('id')), key.get('name'), key.get('idx'))
        nodes = self.build_priority_list(self.nodes_set, key_id)
        stored = False
        for node in nodes:
            if not node.connected:
                try:
                    await asyncio.wait_for(node.connect(), 2)
                except asyncio.TimeoutError:
                    continue
            try:
                resp = await node.store_value(dht_value)
                assert resp[0]['@type'] == 'dht.stored'
                stored = True
            except asyncio.exceptions.TimeoutError:
                continue
            except Exception as e:
                raise e  # ?
            stored = True

        if try_find_after:
            try:
                await self.find_value(key_id, timeout=10)
            except asyncio.exceptions.TimeoutError:
                return False
            except DhtValueNotFoundError:
                return False

        return stored

    @staticmethod
    def get_dht_key(id_: bytes, name: bytes = b'address', idx: int = 0):
        return {'id': id_.hex(), 'name': name, 'idx': idx}

    async def store_value(self, key: dict, value: bytes, private_key: bytes,
                          update_rule: typing.Literal['signature', 'anybody', 'overlayNodes'] = 'signature',
                          ttl: int = 30, try_find_after: bool = True):
        if update_rule != 'signature':
            raise DhtError('currently overlay is not supported')
        pk = Client(ed25519_private_key=private_key)
        key_description = {
            'key': key,
            'id': {
                '@type': 'pub.ed25519',
                'key': pk.ed25519_public.encode().hex()
            },
            'update_rule': self.schemas.get_by_name('dht.updateRule.' + update_rule).little_id(),
            'signature': b''
        }
        signature = pk.sign(self.schemas.serialize(self.schemas.get_by_name('dht.keyDescription'), key_description))

        data = {
            'key': key_description | {'signature': signature},
            'value': value,
            'ttl': int(time.time()) + ttl,
            'signature': b''
        }
        signature = pk.sign(self.schemas.serialize(self.schemas.get_by_name('dht.value'), data))

        data |= {'signature': signature}
        return await self.raw_store_value(data, try_find_after)

    async def get_overlay_nodes(self, overlay_id: typing.Union[bytes, str], overlay_transport: OverlayTransport):
        resp = await self.find_value(key=self.get_dht_key_id_tl(overlay_id, name=b'nodes'), timeout=30)
        nodes = resp['value']['value']['nodes']
        result = []
        for node in nodes:
            result.append(await self.get_overlay_node(node, overlay_transport))
        return result

    async def get_overlay_node(self, node: dict, overlay_transport: OverlayTransport) -> typing.Optional[OverlayNode]:
        """
        :param node: dict overlay.node TL schema
        :param overlay_transport:
        :return: OverlayNode or None
        """
        pub_k = bytes.fromhex(node['id']['key'])
        adnl_addr = Server('', 0, pub_key=pub_k).get_key_id()

        to_sign = self.schemas.serialize(
            schema=self.schemas.get_by_name('overlay.node.toSign'),
            data={'id': {'id': adnl_addr.hex()}, 'overlay': node['overlay'], 'version': node['version']}
        )

        if not verify_sign(pub_k, to_sign, node['signature']):
            raise Exception('invalid node signature!')

        try:
            resp = await self.find_value(key=self.get_dht_key_id_tl(id_=adnl_addr), timeout=5)
        except asyncio.TimeoutError:
            return None

        node_addr = resp['value']['value']['addrs'][0]
        host = socket.inet_ntoa(struct.pack('>i', node_addr['ip']))
        port = node_addr['port']
        pub_k = base64.b64encode(bytes.fromhex(resp['value']['key']['id']['key'])).decode()

        node = OverlayNode(peer_host=host, peer_port=port, peer_pub_key=pub_k, transport=overlay_transport)
        return node

    @classmethod
    def from_config(cls, config: dict, adnl_transport: AdnlTransport):
        nodes = []
        nodes_dict = config['dht']['static_nodes']['nodes']
        for node in nodes_dict:
            nodes.append(DhtNode.from_dict(adnl_transport, node))
        return cls(nodes, adnl_transport)

    @classmethod
    def from_mainnet_config(cls, adnl_transport: AdnlTransport):
        config = requests.get('https://ton.org/global-config.json').json()
        return cls.from_config(config, adnl_transport)

    @classmethod
    def from_testnet_config(cls, adnl_transport: AdnlTransport):
        config = requests.get('https://ton.org/testnet-global.config.json').json()
        return cls.from_config(config, adnl_transport)
