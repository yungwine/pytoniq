import asyncio
import logging
import random
import time
import typing

import requests
from pytoniq_core import BlockIdExt, Block, Address, Account, ShardAccount, SimpleAccount, ShardDescr, Transaction
from pytoniq_core.tlb.block import BinTree

from .client import LiteClient, LiteClientError


class BalancerError(LiteClientError):
    pass


class LiteBalancer:

    def __init__(self, peers: typing.List[LiteClient], timeout: int = 10):

        self._peers = peers
        self._alive_peers: typing.Set[int] = set()

        self._checker: asyncio.Task = None

        self._mc_blocks = {}  # {index: masterchain_seqno}
        self._av_resp_time = {}  # {index: average_response_time}
        self._total_req_num = {}  # {index: successful_requests_num}
        self._current_req_num = {}  # {index: current_waiting_requests_num}

        self._archival_peers = set()

        self._logger = logging.getLogger(self.__class__.__name__)

        self.max_req_per_peer = 100
        self.max_retries = 1
        self.timeout = timeout

    @property
    def inited(self):
        return bool(self._alive_peers)

    def set_max_retries(self, retries_num: int) -> None:
        self.max_retries = retries_num

    async def start_up(self):
        have_blockstore = False
        tasks = []
        for client in self._peers:
            if client.trust_level >= 1:
                tasks.append(self._connect_to_peer(client))
            elif have_blockstore:
                tasks.append(self._connect_to_peer(client))
            else:  # so we can verify blocks proof link only once
                connected = await self._connect_to_peer(client)
                if connected:
                    have_blockstore = True

                async def f(): return connected
                tasks.append(f())
        result = await asyncio.gather(*tasks)
        for i, client in enumerate(self._peers):
            if result[i]:
                self._alive_peers.add(i)
        await self._find_archives()
        self._checker = asyncio.create_task(self._check_peers())

    async def _find_archives(self):
        tasks = []
        inds = []
        for i in self._alive_peers:
            tasks.append(self.check_archive(self._peers[i]))
            inds.append(i)

        result = await asyncio.gather(*tasks, return_exceptions=True)
        for i, r in enumerate(result):
            if isinstance(r, bool):
                if r:
                    self._archival_peers.add(inds[i])
                else:
                    self._archival_peers.discard(inds[i])  # almost impossible case when peer becomes unarchival
            elif isinstance(r, Exception):
                self._logger.info(f'Failed to check peer {inds[i]} on archival: {r}')

    @staticmethod
    async def check_archive(peer: LiteClient):
        try:
            blk, _ = await peer.lookup_block(wc=-1, shard=-2**63, seqno=random.randint(1, 1024))  # as ton-http-api does, but maybe need to ask the first block. todo
            return True
        except LiteClientError:
            return False

    async def _connect_to_peer(self, client: LiteClient):
        if client.listener is not None and not client.listener.done():
            await client.close()
        try:
            if client.trust_level >= 1:
                await asyncio.wait_for(client.connect(), 3)
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
            await asyncio.wait_for(peer.get_masterchain_info(), 3)
            return True
        except asyncio.TimeoutError:
            return False
        except Exception as e:
            self._logger.debug(f'Failed to ping peer {peer.server.get_key_id().hex()}: {e}')

    async def _check_peers(self):
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

    async def connect(self):
        raise BalancerError(f'Use start_up()')

    def _build_priority_list(self, only_archive: bool = False):
        sorted_peers = sorted(
            list(self._alive_peers) if not only_archive else list(self._archival_peers),
            key=lambda e: (self._mc_blocks.get(e, 0), -self._av_resp_time.get(e, self.timeout * 1000)),
            reverse=True
        )  # first peers are with biggest masterchain seqno and lowest avg time response
        return sorted_peers

    def _choose_peer(self, only_archive: bool = False):
        peers = self._build_priority_list(only_archive)
        min_req = float('inf')
        for p in peers:
            peer_req = self._current_req_num.get(p, 0)
            if peer_req <= self.max_req_per_peer:
                return p
            if peer_req < min_req:
                min_req = peer_req
        for p in peers:
            peer_req = self._current_req_num.get(p, 0)
            if peer_req <= min_req:
                return p
        return peers[0]  # should never happen

    @staticmethod
    def _calc_new_average(old_average: int, n: int, new_value: int):
        return (old_average * (n - 1) + new_value) / n

    def _update_average_request_time(self, ls_index: int, req_time: int):
        old = self._av_resp_time.get(ls_index, 0)
        req_num = self._total_req_num.get(ls_index, 0)
        req_num += 1
        self._av_resp_time[ls_index] = self._calc_new_average(old, req_num, req_time)
        self._total_req_num[ls_index] = req_num

    def _update_mc_seqno(self, ls_index: int):
        client = self._peers[ls_index]
        blk = client.last_mc_block
        if blk and self._mc_blocks.get(ls_index, 0) < blk.seqno:
            self._mc_blocks[ls_index] = blk.seqno

    def _update_mc_seqnos(self):
        for i in range(len(self._peers)):
            self._update_mc_seqno(i)

    async def execute_method(self, method_name_: str, *args, **kwargs) -> typing.Union[dict, typing.Any]:
        for _ in range(self.max_retries):

            if not len(self._alive_peers):
                raise BalancerError(f'have no alive peers')

            only_archive = kwargs.pop('only_archive', False)
            if only_archive and not len(self._archival_peers):
                await self._find_archives()  # give one more chance to find
                if not len(self._archival_peers):
                    raise BalancerError(f'have no alive archive peers')

            self._update_mc_seqnos()
            ind = self._choose_peer(only_archive)
            peer: LiteClient = self._peers[ind]

            peer_meth = getattr(peer, method_name_, None)
            self._current_req_num[ind] = self._current_req_num.get(ind, 0) + 1
            s = time.time_ns()
            if not peer_meth:
                raise BalancerError('Unknown method for peer')

            try:
                resp = await peer_meth(*args, **kwargs)
                self._update_average_request_time(ind, (time.time_ns() - s) // 10**6)  # provide milliseconds
                return resp
            except asyncio.TimeoutError:
                self._alive_peers.discard(ind)
                continue
            finally:
                self._current_req_num[ind] -= 1

    @staticmethod
    def _get_args(locals_: dict):
        a = locals_.copy()
        a.pop('self')
        kwargs = a.pop('kwargs', {})
        a |= kwargs
        return a

    """CODE BELOW IS AUTOGENERATED. DO NOT EDIT MANUALLY"""

    async def get_masterchain_info(self, **kwargs):
        return await self.execute_method('get_masterchain_info', **self._get_args(locals())) 

    async def raw_wait_masterchain_seqno(self, seqno: int, timeout_ms: int, suffix: bytes = b'', **kwargs):
        return await self.execute_method('raw_wait_masterchain_seqno', **self._get_args(locals())) 

    async def wait_masterchain_seqno(self, seqno: int, timeout_ms: int, schema_name: str, data: dict = None, **kwargs):
        return await self.execute_method('wait_masterchain_seqno', **self._get_args(locals())) 

    async def get_masterchain_info_ext(self, **kwargs):
        return await self.execute_method('get_masterchain_info_ext', **self._get_args(locals())) 

    async def get_time(self, **kwargs):
        return await self.execute_method('get_time', **self._get_args(locals())) 

    async def get_version(self, **kwargs):
        return await self.execute_method('get_version', **self._get_args(locals())) 

    async def get_state(self, wc: int, shard: typing.Optional[int],
                        seqno: int, root_hash: typing.Union[str, bytes],
                        file_hash: typing.Union[str, bytes]
                        , **kwargs) -> dict:
        return await self.execute_method('get_state', **self._get_args(locals())) 

    async def raw_get_block_header(self, block: BlockIdExt, **kwargs) -> Block:
        return await self.execute_method('raw_get_block_header', **self._get_args(locals())) 

    async def get_block_header(self, wc: int, shard: typing.Optional[int], seqno: int,
                               root_hash: typing.Union[str, bytes],
                               file_hash: typing.Union[str, bytes]
                               , **kwargs) -> Block:
        return await self.execute_method('get_block_header', **self._get_args(locals())) 

    async def lookup_block(self, wc: int, shard: int, seqno: int = -1,
                           lt: typing.Optional[int] = None,
                           utime: typing.Optional[int] = None, **kwargs) -> typing.Tuple[BlockIdExt, Block]:
        return await self.execute_method('lookup_block', **self._get_args(locals())) 

    async def raw_get_block(self, block: BlockIdExt, **kwargs) -> Block:
        return await self.execute_method('raw_get_block', **self._get_args(locals())) 

    async def get_block(self, wc: int, shard: typing.Optional[int],
                        seqno: int, root_hash: typing.Union[str, bytes],
                        file_hash: typing.Union[str, bytes], **kwargs) -> Block:
        return await self.execute_method('get_block', **self._get_args(locals())) 

    async def raw_get_account_state(self, address: typing.Union[str, Address],
                                    block: typing.Optional[BlockIdExt] = None
                                    , **kwargs) -> typing.Tuple[typing.Optional[Account], typing.Optional[ShardAccount]]:
        return await self.execute_method('raw_get_account_state', **self._get_args(locals())) 

    async def get_account_state(self, address: typing.Union[str, Address], **kwargs) -> SimpleAccount:
        return await self.execute_method('get_account_state', **self._get_args(locals())) 

    async def run_get_method(self, address: typing.Union[Address, str],
                             method: typing.Union[int, str], stack: list,
                             block: BlockIdExt = None
                             , **kwargs) -> list:
        return await self.execute_method('run_get_method', **self._get_args(locals())) 

    async def raw_get_shard_info(self, block: typing.Optional[BlockIdExt] = None,
                                 wc: int = 0, shard: int = -9223372036854775808,
                                 exact: bool = True
                                 , **kwargs) -> ShardDescr:
        return await self.execute_method('raw_get_shard_info', **self._get_args(locals())) 

    async def raw_get_all_shards_info(self, block: typing.Optional[BlockIdExt] = None, **kwargs) -> typing.Dict[int, BinTree]:
        return await self.execute_method('raw_get_all_shards_info', **self._get_args(locals())) 

    async def get_all_shards_info(self, block: typing.Optional[BlockIdExt] = None, **kwargs) -> typing.List[BlockIdExt]:
        return await self.execute_method('get_all_shards_info', **self._get_args(locals())) 

    async def get_one_transaction(self, address: typing.Union[Address, str],
                                  lt: int, block: BlockIdExt
                                  , **kwargs) -> typing.Optional[Transaction]:
        return await self.execute_method('get_one_transaction', **self._get_args(locals())) 

    async def raw_get_transactions(self, address: typing.Union[Address, str], count: int,
                                   from_lt: int = None, from_hash: typing.Optional[bytes] = None
                                   , **kwargs) -> typing.Tuple[typing.List[Transaction], typing.List[BlockIdExt]]:
        return await self.execute_method('raw_get_transactions', **self._get_args(locals())) 

    async def get_transactions(self, address: typing.Union[Address, str], count: int,
                               from_lt: int = None, from_hash: typing.Optional[bytes] = None
                               , **kwargs) -> typing.List[Transaction]:
        return await self.execute_method('get_transactions', **self._get_args(locals())) 

    async def raw_get_block_transactions(self, block: BlockIdExt, count: int = 1024, **kwargs) -> typing.List[dict]:
        return await self.execute_method('raw_get_block_transactions', **self._get_args(locals())) 

    async def raw_get_block_transactions_ext(self, block: BlockIdExt, count: int = 1024, **kwargs) -> typing.List[Transaction]:
        return await self.execute_method('raw_get_block_transactions_ext', **self._get_args(locals())) 

    async def raw_get_mc_block_proof(self, known_block: BlockIdExt, target_block: typing.Optional[BlockIdExt] = None,
                                     return_best_key_block=False
                                     , **kwargs) -> typing.Tuple[
                                                        bool,
                                                        BlockIdExt,
                                                        typing.Optional[BlockIdExt],
                                                        typing.Optional[int]
                                        ]:
        return await self.execute_method('raw_get_mc_block_proof', **self._get_args(locals())) 

    async def get_mc_block_proof(self, known_block: BlockIdExt,
                                 target_block: BlockIdExt,
                                 return_best_key_block=False
                                 , **kwargs) -> typing.Tuple[typing.Optional[BlockIdExt], int]:
        return await self.execute_method('get_mc_block_proof', **self._get_args(locals())) 

    async def prove_block(self, target_block: BlockIdExt, **kwargs) -> None:
        return await self.execute_method('prove_block', **self._get_args(locals())) 

    async def get_config_all(self, blk: typing.Optional[BlockIdExt] = None, **kwargs) -> dict:
        return await self.execute_method('get_config_all', **self._get_args(locals())) 

    async def get_config_params(self, params: typing.List[int], blk: typing.Optional[BlockIdExt] = None, **kwargs) -> dict:
        return await self.execute_method('get_config_params', **self._get_args(locals())) 

    async def get_libraries(self, library_list: typing.List[bytes], **kwargs):
        return await self.execute_method('get_libraries', **self._get_args(locals())) 

    async def get_shard_block_proof(self, blk: BlockIdExt, prove_mc: bool = False, **kwargs):
        return await self.execute_method('get_shard_block_proof', **self._get_args(locals())) 

    async def raw_send_message(self, message: bytes, **kwargs):
        return await self.execute_method('raw_send_message', **self._get_args(locals())) 

    """CODE ABOVE IS AUTOGENERATED. DO NOT EDIT MANUALLY"""

    async def close_all(self):
        for peer in self._peers:
            if peer.inited:
                await peer.close()
        self._checker.cancel()
        while not self._checker.cancelled():
            await asyncio.sleep(0)

    async def close(self):
        raise BalancerError('Use .close_all()')

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
