import asyncio.exceptions
import time
import typing
import hashlib
from functools import cmp_to_key

from pytoniq_core.tl import TlGenerator

from .udp_client import AdnlUdpClient


class DhtError(Exception):
    pass


class DhtValueNotFoundError(DhtError):
    pass


class DhtClient:

    def __init__(self,
                 nodes: typing.List[AdnlUdpClient],
                 tl_schemas_path: typing.Optional[str] = None
                 ):
        self.nodes = nodes
        self.nodes_set: set = set(nodes)
        assert len(nodes) >= 1, 'expected at least 1 node in the list'
        if tl_schemas_path is None:
            self.schemas = nodes[0].schemas
            # self.schemas = TlGenerator.with_default_schemas().generate()
        else:
            self.schemas = TlGenerator(tl_schemas_path).generate()

    async def connect(self, node_index: int):
        await self.nodes[node_index].connect()

    def get_dht_key_id_tl(self, id_: bytes, name: str = 'address', idx: int = 0):
        dht_key_sch = self.schemas.get_by_name('dht.key')
        serialized = self.schemas.serialize(dht_key_sch, data={'id': id_.hex(), 'name': name.encode(), 'idx': idx})
        return hashlib.sha256(serialized).digest()

    @staticmethod
    def get_dht_key_id(id_: bytes, name: str = 'address', idx: int = 0):
        """
        Same as the method above but without using TlGenerator
        """
        bytes_name = name.encode()
        to_hash = b'\x8f\xdeg\xf6' + id_ + len(bytes_name).to_bytes(1, 'big') + bytes_name + idx.to_bytes(4, 'little')
        return hashlib.sha256(to_hash).digest()

    @staticmethod
    def find_distance_between_nodes(key_id_1: typing.Union[bytes, int], key_id_2: typing.Union[bytes, int]):
        if isinstance(key_id_1, bytes):
            key_id_1 = int.from_bytes(key_id_1, 'big')
        if isinstance(key_id_2, bytes):
            key_id_2 = int.from_bytes(key_id_2, 'big')
        return key_id_1 ^ key_id_2

    async def find_value(self, key: bytes, k: int = 6, timeout: int = 10):
        start_time = time.time()
        while True:
            if time.time() - start_time > timeout:
                raise asyncio.exceptions.TimeoutError
            nodes: typing.List[AdnlUdpClient] = sorted(self.nodes_set, key=lambda i: self.find_distance_between_nodes(i.peer_id, key))
            for node in nodes:
                try:
                    await node.connect()
                    resp = await node.dht_find_value(key=key, k=k)
                    if resp['@type'] == 'dht.valueNotFound':
                        new_nodes = resp['nodes']['nodes']
                        new_nodes_set = set()
                        for n in new_nodes:
                            new_nodes_set.add(AdnlUdpClient.from_dict(n, timeout=0.5))
                        old_nodes = self.nodes_set.copy()
                        self.nodes_set = self.nodes_set.union(new_nodes_set)
                        if self.nodes_set == old_nodes:
                            raise DhtValueNotFoundError(f'value {key.hex()} not found')
                        break
                    elif resp['@type'] == 'dht.valueFound':
                        return resp
                    else:
                        raise DhtError(f'received unknown response type: {resp}')
                except asyncio.exceptions.TimeoutError:
                    continue
                finally:
                    await node.close()
