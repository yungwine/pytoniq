import asyncio
import logging
import random
import typing

import requests
from pytoniq_core import TlGenerator, BlockIdExt, Block, Address, Account, ShardAccount, SimpleAccount, ShardDescr, \
    Transaction
from pytoniq_core.tlb.block import BinTree

from .client import LiteClient, LiteClientError


class BalancerError(LiteClientError):
    pass


class LiteBalancer:

    def __init__(self, peers: typing.List[LiteClient], max_retries: int = 10, timeout: int = 10):
        self._peers = peers
        self._alive_peers: typing.Set[int] = set()
        self._logger = logging.getLogger(self.__class__.__name__)

        self.max_retries = max_retries
        self.timeout = timeout

    @property
    def inited(self):
        return bool(self._alive_peers)

    async def start_up(self):
        have_blockstore = False
        tasks = []
        for i, client in enumerate(self._peers):
            if client.trust_level >= 1:
                tasks.append(self._connect_to_peer(client))
            elif have_blockstore:
                tasks.append(self._connect_to_peer(client))
            else:
                connected = await self._connect_to_peer(client)

                if connected:
                    have_blockstore = True

                async def f(): return connected
                tasks.append(f())

        result = await asyncio.gather(*tasks)
        for i, client in enumerate(self._peers):
            if result[i]:
                self._alive_peers.add(i)

        asyncio.create_task(self.check_peers())

    async def _connect_to_peer(self, client: LiteClient):
        if client.listener is not None and not client.listener.done():
            await client.close()
        try:
            if client.trust_level >= 1:
                await asyncio.wait_for(client.connect(), 2)
            else:
                await client.connect()
            return True
        except asyncio.TimeoutError:
            return False
        except Exception as e:
            self._logger.debug(f'Failed to connect to the peer {client.server.get_key_id().hex()}: {e}')
            return False

    async def _ping_peer(self, peer: LiteClient):
        try:
            await asyncio.wait_for(peer.get_masterchain_info(), 2)
            return True
        except asyncio.TimeoutError:
            return False
        except Exception as e:
            self._logger.debug(f'Failed to ping peer {peer.server.get_key_id().hex()}: {e}')

    async def check_peers(self):
        while True:
            await asyncio.sleep(3)
            for i, client in enumerate(self._peers):
                client: LiteClient
                if client.inited:
                    if client.updater.done() or client.listener.done() or client.pinger.done():
                        if client.updater.done():
                            self._logger.debug(f'client {i} updater failed with exc {client.updater.exception()}')
                        if client.listener.done():
                            self._logger.debug(f'client {i} listener failed with exc {client.listener.exception()}')
                        if client.pinger.done():
                            self._logger.debug(f'client {i} pinger failed with exc {client.pinger.exception()}')
                        self._alive_peers.discard(i)
                        await client.close()
                        if await self._connect_to_peer(client):
                            self._alive_peers.add(i)
                        else:
                            self._alive_peers.discard(i)
                    ping_res = await self._ping_peer(client)
                    if ping_res:
                        self._alive_peers.add(i)
                    else:
                        self._alive_peers.discard(i)
                else:
                    if await self._connect_to_peer(client):
                        self._alive_peers.add(i)
                    else:
                        self._alive_peers.discard(i)

    @classmethod
    def from_config(cls, config: dict, trust_level: int = 2, timeout: int = 10):
        clients = []
        for i in range(len(config['liteservers'])):
            clients.append(LiteClient.from_config(config, i, trust_level, timeout))
        return cls(clients)

    @classmethod
    def from_mainnet_config(cls, trust_level: int = 0, timeout: int = 10):
        config = requests.get('https://ton.org/global-config.json').json()
        return cls.from_config(config, trust_level, timeout)

    @classmethod
    def from_testnet_config(cls, trust_level: int = 0, timeout: int = 10):
        config = requests.get('https://ton.org/testnet-global.config.json').json()
        return cls.from_config(config, trust_level, timeout)

    async def connect(self):
        raise BalancerError(f'Use start_up()')

    async def execute_method(self, method: str, *args, **kwargs) -> typing.Union[dict, typing.Any]:
        for i in range(self.max_retries):
            if not len(self._alive_peers):
                raise BalancerError(f'have no alive peers')
            ind = random.choice(list(self._alive_peers))
            peer: LiteClient = self._peers[ind]
            peer_meth = getattr(peer, method, None)
            if not peer_meth:
                raise BalancerError('Unknown method for peer')
            try:
                return await peer_meth(*args, **kwargs)
            except (LiteClientError, asyncio.TimeoutError):
                continue

    @staticmethod
    def _get_args(locals_: dict):
        a = locals_.copy()
        a.pop('self')
        return a

    async def get_masterchain_info(self) -> dict:
        return await self.execute_method('get_masterchain_info')

    async def raw_wait_masterchain_seqno(self, seqno: int, timeout_ms: int, suffix: bytes = b'') -> dict:
        return await self.execute_method('raw_wait_masterchain_seqno', **self._get_args(locals()))

    async def wait_masterchain_seqno(self, seqno: int, timeout_ms: int, schema_name: str, data: dict = None) -> dict:
        return await self.execute_method('wait_masterchain_seqno', **self._get_args(locals()))

    async def get_masterchain_info_ext(self):
        return await self.execute_method('get_masterchain_info_ext')

    async def get_time(self):
        raise BalancerError('Use LiteClient')

    async def get_version(self):
        raise BalancerError('Use LiteClient')

    async def get_state(self, wc: int, shard: typing.Optional[int], seqno: int, root_hash: typing.Union[str, bytes], file_hash: typing.Union[str, bytes]):
        return await self.execute_method('get_state', **self._get_args(locals()))

    async def raw_get_block_header(self, block: BlockIdExt) -> Block:
        return await self.execute_method('raw_get_block_header', **self._get_args(locals()))

    async def lookup_block(self, wc: int, shard: int, seqno: int = -1,
                           lt: typing.Optional[int] = None,
                           utime: typing.Optional[int] = None) -> typing.Tuple[BlockIdExt, Block]:
        return await self.execute_method('lookup_block', **self._get_args(locals()))

    async def raw_get_block(self, block: BlockIdExt) -> Block:
        return await self.execute_method('raw_get_block', **self._get_args(locals()))

    async def get_block(self,
                        wc: int, shard: typing.Optional[int],
                        seqno: int, root_hash: typing.Union[str, bytes],
                        file_hash: typing.Union[str, bytes]) -> Block:
        return await self.execute_method('get_block', **self._get_args(locals()))

    async def raw_get_account_state(self,
                                    address: typing.Union[str, Address],
                                    block: typing.Optional[BlockIdExt] = None
                                    ) -> typing.Tuple[typing.Optional[Account], typing.Optional[ShardAccount]]:
        return await self.execute_method('raw_get_account_state', **self._get_args(locals()))

    async def get_account_state(self, address: typing.Union[str, Address]) -> SimpleAccount:
        return await self.execute_method('get_account_state', **self._get_args(locals()))

    async def run_get_method(self,
                             address: typing.Union[Address, str],
                             method: typing.Union[int, str], stack: list,
                             block: BlockIdExt = None
                             ) -> list:
        return await self.execute_method('get_account_state', **self._get_args(locals()))

    async def raw_get_shard_info(self,
                                 block: typing.Optional[BlockIdExt] = None,
                                 wc: int = 0, shard: int = -9223372036854775808,
                                 exact: bool = True
                                 ) -> ShardDescr:
        return await self.execute_method('raw_get_shard_info', **self._get_args(locals()))

    async def raw_get_all_shards_info(self, block: typing.Optional[BlockIdExt] = None) -> typing.Dict[int, BinTree]:
        return await self.execute_method('raw_get_all_shards_info', **self._get_args(locals()))

    async def get_all_shards_info(self, block: typing.Optional[BlockIdExt] = None) -> typing.List[BlockIdExt]:
        return await self.execute_method('get_all_shards_info', **self._get_args(locals()))

    async def get_one_transaction(self,
                                  address: typing.Union[Address, str],
                                  lt: int, block: BlockIdExt
                                  ) -> typing.Optional[Transaction]:

        return await self.execute_method('get_one_transaction', **self._get_args(locals()))

    async def raw_get_transactions(self,
                                   address: typing.Union[Address, str], count: int,
                                   from_lt: int = None, from_hash: typing.Optional[bytes] = None
                                   ) -> typing.Tuple[typing.List[Transaction], typing.List[BlockIdExt]]:
        return await self.execute_method('raw_get_transactions', **self._get_args(locals()))

    async def get_transactions(self,
                               address: typing.Union[Address, str], count: int,
                               from_lt: int = None, from_hash: typing.Optional[bytes] = None
                               ) -> typing.List[Transaction]:
        return await self.execute_method('get_transactions', **self._get_args(locals()))

    async def raw_get_block_transactions(self, block: BlockIdExt, count: int = 256) -> typing.List[dict]:
        return await self.execute_method('raw_get_block_transactions', **self._get_args(locals()))

    async def raw_get_block_transactions_ext(self, block: BlockIdExt, count: int = 256) -> typing.List[Transaction]:
        return await self.execute_method('raw_get_block_transactions_ext', **self._get_args(locals()))

    async def raw_get_mc_block_proof(self,
                                     known_block: BlockIdExt, target_block: typing.Optional[BlockIdExt] = None,
                                     return_best_key_block=False
                                     ) -> typing.Tuple[
                                                        bool,
                                                        BlockIdExt,
                                                        typing.Optional[BlockIdExt],
                                                        typing.Optional[int]
                                        ]:
        return await self.execute_method('raw_get_mc_block_proof', **self._get_args(locals()))

    async def get_mc_block_proof(self,
                                 known_block: BlockIdExt,
                                 target_block: BlockIdExt,
                                 return_best_key_block=False
                                 ) -> typing.Tuple[typing.Optional[BlockIdExt], int]:
        return await self.execute_method('get_mc_block_proof', **self._get_args(locals()))

    async def prove_block(self, target_block: BlockIdExt) -> None:
        return await self.execute_method('prove_block', **self._get_args(locals()))

    async def get_config_all(self, blk: typing.Optional[BlockIdExt] = None) -> dict:
        return await self.execute_method('get_config_all', **self._get_args(locals()))

    async def get_config_params(self, params: typing.List[int], blk: typing.Optional[BlockIdExt] = None) -> dict:
        return await self.execute_method('get_config_params', **self._get_args(locals()))

    async def get_libraries(self, library_list: typing.List[bytes]):
        return await self.execute_method('get_libraries', **self._get_args(locals()))

    async def get_shard_block_proof(self, blk: BlockIdExt, prove_mc: bool = False):
        return await self.execute_method('get_shard_block_proof', **self._get_args(locals()))

    async def raw_send_message(self, message: bytes):
        return await self.execute_method('raw_send_message', **self._get_args(locals()))
