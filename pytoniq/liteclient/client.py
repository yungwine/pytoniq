import base64
import hashlib
import logging
import os
import asyncio
import socket
import struct
import typing

import requests

from .sync import persistent_state_ttl, choose_key_block, sync
from .utils import init_mainnet_block, init_testnet_block
from ..boc import Slice, Cell, Builder
from ..proof.check_proof import check_block_header_proof, check_shard_proof, check_account_proof, check_proof, \
    check_block_signatures, compute_validator_set
from ..boc.address import Address

# from .crypto import ed25519Public, ed25519Private, x25519Public, x25519Private
from ..crypto.ciphers import Server, Client, get_random, create_aes_ctr_cipher, aes_ctr_encrypt, aes_ctr_decrypt, get_shared_key
from ..crypto.crc import crc16

from ..tl.generator import TlGenerator, TlSchema
from ..tl.block import BlockId, BlockIdExt
from ..tlb.config import ConfigParam34, ConfigParam28, ConfigParam
from ..tlb.transaction import Transaction
from ..tlb.utils import deserialize_shard_hashes

from ..tlb.vm_stack import VmStack
from ..tlb.block import Block, ShardDescr, BinTree, ShardStateUnsplit, KeyExtBlkRef
from ..tlb.account import Account, SimpleAccount, ShardAccount, AccountBlock


class LiteClientError(BaseException):
    pass


class RunGetMethodError(LiteClientError):
    pass


class LiteClient:

    def __init__(self,
                 host: str,  # ipv4 host
                 port: int,
                 server_pub_key: str,  # server ed25519 public key in base64,
                 tl_schemas_path: typing.Optional[str] = None,
                 trust_level: int = 1,
                 init_key_block: BlockIdExt = None,
                 ) -> None:

        """########### init ###########"""
        self.tasks = {}
        self.inited = False
        self.logger = logging.getLogger(self.__class__.__name__)

        """########### sync ###########"""
        self.last_mc_block: BlockIdExt = None
        self.last_shard_blocks: typing.Dict[int, BlockIdExt] = None
        self.last_key_block: BlockIdExt = None
        self.trust_level = trust_level
        self.init_key_block: BlockIdExt = init_key_block
        if not self.trust_level and not init_key_block:
            raise LiteClientError('trust level is zero but no init block provided')

        """########### crypto ###########"""
        self.server = Server(host, port, base64.b64decode(server_pub_key))
        self.client = Client(Client.generate_ed25519_private_key())
        self.enc_sipher = None
        self.dec_sipher = None

        """########### connection ###########"""
        self.reader: asyncio.StreamReader = None
        self.writer: asyncio.StreamWriter = None
        self.listener: asyncio.Task = None
        self.pinger: asyncio.Task = None
        self.updater: asyncio.Task = None
        self.loop = asyncio.get_event_loop()
        self.delta = 0.1  # listen delay

        """########### TL ###########"""
        if tl_schemas_path is None:
            tl_schemas_path = os.path.join(os.path.dirname(__file__), os.pardir, 'tl/schemas')
        self.schemas = TlGenerator(tl_schemas_path).generate()
        # for better performance:
        self.ping_sch = self.schemas.get_by_name('tcp.ping')
        self.pong_sch = self.schemas.get_by_name('tcp.pong')
        self.adnl_query_sch = self.schemas.get_by_name('adnl.message.query')
        self.ls_query_sch = self.schemas.get_by_name('liteServer.query')

    def encrypt(self, data: bytes) -> bytes:
        return aes_ctr_encrypt(self.enc_sipher, data)

    def decrypt(self, data: bytes) -> bytes:
        return aes_ctr_decrypt(self.dec_sipher, data)

    async def send(self, data: bytes, qid: typing.Union[str, int, None]) -> asyncio.Future:
        future = self.loop.create_future()
        self.writer.write(data)
        await self.writer.drain()
        self.tasks[qid] = future
        return future

    async def send_and_encrypt(self, data: bytes, qid: str) -> asyncio.Future:
        future = self.loop.create_future()
        self.writer.write(self.encrypt(data))
        await self.writer.drain()
        self.tasks[qid] = future
        return future

    async def receive(self, data_len: int) -> bytes:
        data = await self.reader.readexactly(data_len)
        return data

    async def receive_and_decrypt(self, data_len: int) -> bytes:
        data = self.decrypt(await self.receive(data_len))
        return data

    async def listen(self) -> None:
        while True:
            while not self.tasks:
                await asyncio.sleep(self.delta)

            data_len_encrypted = await self.receive(4)
            data_len = int(self.decrypt(data_len_encrypted)[::-1].hex(), 16)

            self.logger.debug(msg=f'received {data_len // 8} bytes of data')

            data_encrypted = await self.receive(data_len)
            data_decrypted = self.decrypt(data_encrypted)
            # check hashsum
            assert hashlib.sha256(data_decrypted[:-32]).digest() == data_decrypted[-32:], 'incorrect checksum'
            result = self.deserialize_adnl_query(data_decrypted[:-32])

            if not result:
                # for handshake
                result = {}
            if 'code' in result and 'message' in result:
                raise LiteClientError(f'LiteClient crashed with {result["code"]} code. Message: {result["message"]}')

            qid = result.get('query_id', result.get('random_id'))  # return query_id for ordinary requests, random_id for ping-pong requests, None for handshake

            request = self.tasks.pop(qid)
            request.set_result(result.get('answer', {}))

    async def connect(self) -> None:
        handshake = self.handshake()
        self.reader, self.writer = await asyncio.open_connection(self.server.host, self.server.port)
        future = await self.send(handshake, None)
        self.listener = asyncio.create_task(self.listen(), name='listener')
        await self.update_last_blocks()
        self.pinger = asyncio.create_task(self.ping(), name='pinger')
        self.updater = asyncio.create_task(self.block_updater(), name='updater')
        await future
        self.inited = True

    async def close(self) -> None:
        for i in asyncio.all_tasks(self.loop):
            if i.get_name() in ('pinger', 'listener', 'updater'):
                i.cancel()
        self.logger.info(msg='client has been closed')

    def handshake(self) -> bytes:
        rand = get_random(160)
        self.dec_sipher = create_aes_ctr_cipher(rand[0:32], rand[64:80])
        self.enc_sipher = create_aes_ctr_cipher(rand[32:64], rand[80:96])
        checksum = hashlib.sha256(rand).digest()
        shared_key = get_shared_key(self.client.x25519_private.encode(), self.server.x25519_public.encode())
        init_cipher = create_aes_ctr_cipher(shared_key[0:16] + checksum[16:32], checksum[0:4] + shared_key[20:32])
        data = aes_ctr_encrypt(init_cipher, rand)
        return self.server.get_key_id() + self.client.ed25519_public.encode() + checksum + data

    @staticmethod
    def serialize_packet(data: bytes):
        result = (len(data) + 64).to_bytes(4, 'little')
        result += get_random(32)  # nonce
        result += data  # useful data
        result += hashlib.sha256(result[4:]).digest()  # hashsum
        return result

    def serialize_adnl_ls_query(self, schema: TlSchema, data: dict) -> typing.Tuple[bytes, str]:
        """
        :param schema: TL schema
        :param data: dict
        :return: result_bytes, qid
        """
        qid = get_random(32)
        res = self.schemas.serialize(
            self.adnl_query_sch,
            {'query_id': qid,
             'query': self.schemas.serialize(self.ls_query_sch,
                                             {'data': self.schemas.serialize(schema, data)}
                                             )
             }
        )
        return res, qid[::-1].hex()

    def deserialize_adnl_query(self, data: bytes) -> dict:
        return self.schemas.deserialize(data[32:], boxed=True)[0]

    def get_ping_query(self):
        ping_sch = self.schemas.get_by_name('tcp.ping')
        query_id = get_random(8)
        data = self.schemas.serialize(ping_sch, {'random_id': query_id})
        data = self.serialize_packet(data)
        ping_result = self.encrypt(data)
        return ping_result, int.from_bytes(query_id, 'big', signed=True)

    async def ping(self):
        while True:
            await asyncio.sleep(3)
            ping_query, qid = self.get_ping_query()
            pong = await self.send(ping_query, qid)
            await pong
            self.logger.debug(msg=f'ping - pong')

    async def liteserver_request(self, tl_schema_name: str, data: dict) -> dict:
        schema = self.schemas.get_by_name('liteServer.' + tl_schema_name)
        self.logger.info(msg=f'requesting {tl_schema_name} with provided data {data}')
        data, qid = self.serialize_adnl_ls_query(schema, data)
        data = self.serialize_packet(data)
        resp = await self.send_and_encrypt(data, qid)
        await resp
        return resp.result()

    @staticmethod
    def pack_block_id_ext(**kwargs):
        if not kwargs.get('shard'):
            kwargs['shard'] = -9223372036854775808
        if isinstance(kwargs['root_hash'], bytes):
            kwargs['root_hash'] = kwargs['root_hash'].hex()
        if isinstance(kwargs['file_hash'], bytes):
            kwargs['file_hash'] = kwargs['file_hash'].hex()
        return {'id': {'workchain': kwargs['wc'], 'shard': kwargs['shard'], 'seqno': kwargs['seqno'], 'root_hash': kwargs['root_hash'], 'file_hash': kwargs['file_hash']}}

    async def get_trusted_last_mc_block(self):
        last_block = BlockIdExt.from_dict((await self.get_masterchain_info())['last'])
        if self.trust_level:
            return last_block
        if not self.last_key_block:
            await sync(client=self, init_block=self.init_key_block, to_block=last_block)
        await self.get_mc_block_proof(known_block=self.last_key_block, target_block=last_block)
        return last_block

    async def update_last_blocks(self):
        self.last_mc_block = await self.get_trusted_last_mc_block()
        shards = await self.raw_get_all_shards_info(self.last_mc_block)
        shard_result = {}
        for k, v in shards.items():
            shard: ShardDescr = v.list[0]
            shard_result[k] = BlockIdExt(workchain=k, seqno=shard.seq_no, shard=None, root_hash=shard.root_hash,
                                         file_hash=shard.file_hash)
        self.last_shard_blocks = shard_result
        self.logger.debug(msg=f'update blocks:\nlast_mc_block: {self.last_mc_block}\nlast_shard_blocks: {self.last_shard_blocks}')

    async def block_updater(self):
        if self.last_mc_block is None:
            self.last_mc_block = await self.get_trusted_last_mc_block()
        while True:
            result = await self.wait_masterchain_seqno(self.last_mc_block.seqno + 1, timeout_ms=10000)
            if result['code'] != 0:
                logging.getLogger().warning(f'error response from liteserver in block updater: {result}')
            await self.update_last_blocks()

    async def get_masterchain_info(self):
        return await self.liteserver_request('getMasterchainInfo', {})

    async def wait_masterchain_seqno(self, seqno: int, timeout_ms: int):
        return await self.liteserver_request('waitMasterchainSeqno', {'seqno': seqno, 'timeout_ms': timeout_ms})

    async def get_masterchain_info_ext(self):
        return await self.liteserver_request('getMasterchainInfoExt', {'mode': 0})

    async def get_time(self):
        return await self.liteserver_request('getTime', {})

    async def get_version(self):
        return await self.liteserver_request('getVersion', {})

    async def get_state(self, wc: int, shard: typing.Optional[int], seqno: int, root_hash: typing.Union[str, bytes], file_hash: typing.Union[str, bytes]):
        # TODO doesnt work: {'code': -400, 'message': 'cannot request total state: possibly too large'}
        block = self.pack_block_id_ext(wc=wc, shard=shard, seqno=seqno, root_hash=root_hash, file_hash=file_hash)
        return await self.liteserver_request('getState', block)

    async def raw_get_block_header(self, block: BlockIdExt):
        result = await self.liteserver_request('getBlockHeader', {'id': block.to_dict()} | {'mode': 0})
        h_proof = Cell.one_from_boc(result['header_proof'])
        block_id = BlockIdExt.from_dict(result['id'])
        if self.trust_level <= 1:
            check_block_header_proof(h_proof[0], block_id.root_hash)
        if not self.trust_level:
            if block_id.workchain != -1:
                await self.get_shard_block_proof(block_id)
            else:
                await self.get_mc_block_proof(known_block=self.last_key_block, target_block=block_id)
        return Block.deserialize(h_proof[0].begin_parse())

    async def get_block_header(self, wc: int, shard: typing.Optional[int], seqno: int, root_hash: typing.Union[str, bytes], file_hash: typing.Union[str, bytes]):
        block = self.pack_block_id_ext(wc=wc, shard=shard, seqno=seqno, root_hash=root_hash, file_hash=file_hash)
        return await self.raw_get_block_header(BlockIdExt.from_dict(block))

    async def lookup_block(self, wc: int, shard: int, seqno: int = -1,
                           lt: typing.Optional[int] = None, utime: typing.Optional[int] = None) -> typing.Tuple[BlockIdExt, Block]:
        """
        :param wc: block workchain
        :param shard: block shard
        :param seqno: block seqno
        :param lt: block lt
        :param utime: block unix time
        :return: tuple[blockIdExt: dict, block: Block] (block here contains only BlockInfo)
        """
        mode = 0
        if seqno != -1:
            mode = 1
        if lt is not None:
            mode = 2
        if utime is not None:
            mode = 4

        data = {'mode': mode, 'id': {'workchain': wc, 'shard': shard, 'seqno': seqno}, 'lt': lt, 'utime': utime}

        result = await self.liteserver_request('lookupBlock', data)
        h_proof = Cell.one_from_boc(result['header_proof'])
        block_id = BlockIdExt.from_dict(result['id'])
        if self.trust_level <= 1:
            check_block_header_proof(h_proof[0], block_id.root_hash)
            if not self.trust_level:
                if block_id.workchain != -1:
                    await self.get_shard_block_proof(block_id)
                else:
                    await self.get_mc_block_proof(known_block=self.last_key_block, target_block=block_id)

        return BlockIdExt.from_dict(result['id']), Block.deserialize(h_proof[0].begin_parse())

    async def raw_get_block(self, block: BlockIdExt) -> Block:
        result = await self.liteserver_request('getBlock', {'id': block.to_dict()})
        block_id = BlockIdExt.from_dict(result['id'])
        assert block_id == block
        result_block = Cell.one_from_boc(result['data'])
        if self.trust_level <= 1:
            check_block_header_proof(result_block, block_hash=block.root_hash)
            if not self.trust_level:
                await self.prove_block(block_id)
        return Block.deserialize(result_block.begin_parse())

    async def get_block(self, wc: int, shard: typing.Optional[int], seqno: int, root_hash: typing.Union[str, bytes], file_hash: typing.Union[str, bytes]):
        block = self.pack_block_id_ext(wc=wc, shard=shard, seqno=seqno, root_hash=root_hash, file_hash=file_hash)
        return await self.raw_get_block(BlockIdExt.from_dict(block))

    async def raw_get_account_state(self, address: typing.Union[str, Address], block: typing.Optional[BlockIdExt] = None) -> typing.Tuple[typing.Optional[Account], typing.Optional[ShardAccount]]:
        trusted = False
        if block is None or block == self.last_mc_block:
            block = self.last_mc_block
            trusted = True
        if isinstance(address, str):
            address = Address(address)
        account = address.to_tl_account_id()

        data = {'id': block.to_dict(), 'account': account}
        result = await self.liteserver_request('getAccountState', data)

        shrd_blk = BlockIdExt.from_dict(result['shardblk'])
        if not result['state']:
            return None, None  # account_none$0 = Account;

        account_state_root = Cell.one_from_boc(result['state'])

        if self.trust_level <= 1:
            check_shard_proof(shard_proof=result['shard_proof'], blk=block, shrd_blk=shrd_blk)
            if not trusted and not self.trust_level:
                await self.get_mc_block_proof(known_block=self.last_key_block, target_block=block)
        shard_account = check_account_proof(proof=result['proof'], shrd_blk=shrd_blk, address=address, account_state_root=account_state_root, return_account_descr=True)

        return Account.deserialize(account_state_root.begin_parse()), shard_account

    async def get_account_state(self, address: typing.Union[str, Address]) -> SimpleAccount:
        """
        :param address: account address
        :return: always SimpleAccount, even if raw_get_account_state returned None (account does not exist)
        """
        if isinstance(address, str):
            address = Address(address)
        return SimpleAccount.from_raw((await self.raw_get_account_state(address))[0], address)

    async def run_get_method(self, address: typing.Union[Address, str], method: typing.Union[int, str], stack: list) -> list:
        mode = 7  # 111
        block = self.last_mc_block

        if isinstance(address, str):
            address = Address(address)
        account = address.to_tl_account_id()

        if isinstance(method, str):
            method_id = (int.from_bytes(crc16(method.encode()), byteorder='big') & 0xffff) | 0x10000
        elif isinstance(method, int):
            method_id = method
        else:
            raise LiteClientError('provided method in unknown form')

        if isinstance(stack, list):
            stack = VmStack.serialize(stack)
        else:
            raise LiteClientError('provided stack in unknown form')

        data = {'mode': mode, 'id': block.to_dict(), 'account': account, 'method_id': method_id, 'params': stack.to_boc()}
        result = await self.liteserver_request('runSmcMethod', data)

        if result['exit_code'] != 0:
            raise RunGetMethodError(f'get method "{method}" for account {address} returned exit code {result["exit_code"]}')
        if self.trust_level <= 1:
            shrd_blk = BlockIdExt.from_dict(result['shardblk'])
            check_shard_proof(shard_proof=result['shard_proof'], blk=block, shrd_blk=shrd_blk)

        return VmStack.deserialize(Slice.one_from_boc(result['result']))

    async def raw_get_shard_info(self, block: typing.Optional[BlockIdExt] = None, wc: int = 0, shard: int = -9223372036854775808, exact: bool = True):
        trusted = False
        if block is None or block == self.last_mc_block:
            block = self.last_mc_block
            trusted = True

        data = {'id': block.to_dict(), 'workchain': wc, 'shard': shard, 'exact': exact}

        result = await self.liteserver_request('getShardInfo', data)
        bin_tree = BinTree.deserialize(Slice.one_from_boc(result['shard_descr']))
        shard_descr = ShardDescr.deserialize(bin_tree.list[0])
        shrd_blk = BlockIdExt.from_dict(result['shardblk'])
        if self.trust_level <= 1:
            shard_descr_proved = check_shard_proof(shard_proof=result['shard_proof'], blk=block, shrd_blk=shrd_blk)
            if not trusted and not self.trust_level:
                await self.get_mc_block_proof(known_block=self.last_key_block, target_block=block)
            if shard_descr_proved is None:
                assert shard_descr_proved == shard_descr

        return shard_descr

    async def raw_get_all_shards_info(self, block: typing.Optional[BlockIdExt] = None) -> typing.Dict[int, BinTree]:
        """
        :param block: blockIdExt
        :return: dict[workchain: BinTree[ShardDescr]]
        """
        trusted = False
        if block is None or block == self.last_mc_block:
            block = self.last_mc_block
            trusted = True

        data = {'id': block.to_dict()}

        result = await self.liteserver_request('getAllShardsInfo', data)

        shard_hashes_cell = Cell.one_from_boc(result['data'])

        if self.trust_level <= 1:

            if not trusted and not self.trust_level:
                await self.get_mc_block_proof(known_block=self.last_key_block, target_block=block)

            proof_cells = Cell.from_boc(result['proof'])

            state_hash = check_block_header_proof(proof_cells[0][0], block_hash=block.root_hash, store_state_hash=True)

            check_proof(proof_cells[1], state_hash)

            shard_state = ShardStateUnsplit.deserialize(proof_cells[1][0].begin_parse())

            assert shard_state.shard_id.workchain_id == block.workchain
            assert shard_state.seq_no == block.seqno

            assert shard_hashes_cell[0].get_hash(0) == proof_cells[1][0][3][0].get_hash(0)  # masterchain_state_extra -> shard_hashes

        return deserialize_shard_hashes(shard_hashes_cell.begin_parse())

    async def get_one_transaction(self, address: typing.Union[Address, str], lt: int, block: BlockIdExt) -> typing.Optional[Transaction]:
        if isinstance(address, str):
            address = Address(address)

        data = {'id': block.to_dict(), 'account': address.to_tl_account_id(), 'lt': lt}
        result = await self.liteserver_request('getOneTransaction', data)
        if not result['transaction']:
            return None

        transaction_root = Cell.one_from_boc(result['transaction'])
        if self.trust_level <= 1:
            proof = Cell.one_from_boc(result['proof'])
            check_block_header_proof(proof[0], block.root_hash)

            acc_block = Block.deserialize(proof[0].begin_parse()).extra.account_blocks[0].get(int.from_bytes(address.hash_part, 'big'))
            if not acc_block:
                raise LiteClientError(f'Proof check failed! Cannot find account in account_blocks')

            acc_block: AccountBlock
            assert acc_block.account_addr == address.hash_part.hex()

            tr = acc_block.transactions[0].get(lt)
            if not tr:
                raise LiteClientError(f'Proof check failed! Cannot find transaction in account block')

            if tr.get_hash(0) != transaction_root.get_hash(0):
                raise LiteClientError(f'Proof check failed! Transaction hashes mismatch')

        return Transaction.deserialize(transaction_root.begin_parse())

    async def raw_get_transactions(self, address: typing.Union[Address, str], count: int, from_lt: int = None, from_hash: typing.Optional[bytes] = None) -> typing.Tuple[typing.List[Transaction], typing.List[BlockIdExt]]:
        if isinstance(address, str):
            address = Address(address)

        assert count <= 16, 'maximum transactions in .raw_get_transactions() is 16!'

        if not from_lt or not from_hash:
            state, shard_account = await self.raw_get_account_state(address)
            from_lt, from_hash = shard_account.last_trans_lt, shard_account.last_trans_hash

        data = {'count': count, 'account': address.to_tl_account_id(), 'lt': from_lt, 'hash': from_hash.hex()}

        result = await self.liteserver_request('getTransactions', data)

        transactions_cells = Cell.from_boc(result['transactions'])

        prev_tr_hash = from_hash

        tr_result = []
        block_ids = []
        i = 0
        for tr in transactions_cells:
            block_ids.append(BlockIdExt.from_dict(result['ids'][i]))
            if self.trust_level <= 1:
                current_hash = tr.get_hash(0)
                if current_hash != prev_tr_hash:
                    raise LiteClientError(f'Transaction hashes mismatch. Expected {prev_tr_hash}, got {current_hash}')
            transaction = Transaction.deserialize(tr.begin_parse())
            prev_tr_hash = transaction.prev_trans_hash
            tr_result.append(transaction)
            i += 1

        # assert len(tr_result) == count, f'expected {count} transactions, got {len(tr_result)}'
        return tr_result, block_ids

    async def get_transactions(self, address: typing.Union[Address, str], count: int, from_lt: int = None, from_hash: typing.Optional[bytes] = None) -> typing.List[Transaction]:
        result: typing.List[Transaction] = []

        for i in range(0, count, 16):
            amount = min(16, count - i)
            tr_result, block_ids = await self.raw_get_transactions(address, amount, from_lt, from_hash)
            result += tr_result
            from_lt, from_hash = result[-1].prev_trans_lt, result[-1].prev_trans_hash
        # assert len(result) == count, f'expected {count} transactions, got {len(result)}'
        return result

    async def raw_get_block_transactions(self, block: BlockIdExt, count: int = 256) -> typing.List[dict]:
        mode = 39  # 100111
        data = {'id': block.to_dict(), 'mode': mode, 'count': count, 'want_proof': b''}
        result = await self.liteserver_request('listBlockTransactions', data)
        if not result['ids']:
            return []
        transactions_ids = result['ids']
        if self.trust_level <= 1:
            proof = Cell.one_from_boc(result['proof'])
            check_block_header_proof(proof[0], block.root_hash)
            acc_block = Block.deserialize(proof[0].begin_parse()).extra.account_blocks[0]

        if not self.trust_level and block != self.last_mc_block:
            await self.prove_block(block)

        for tr in transactions_ids:
            tr['hash'] = bytes.fromhex(tr['hash'])
            tr.pop('mode')  # in this lib mode is a fixed num, so we don't really need it in result, moreover mode can mislead
            if self.trust_level <= 1:
                block_trs: dict = acc_block.get(int(tr['account'], 16)).transactions[0]
                block_tr: Cell = block_trs.get(tr['lt'])
                assert block_tr.get_hash(0) == tr['hash']
            tr['account'] = Address((block.workchain, bytes.fromhex(tr['account'])))

        return transactions_ids

    async def raw_get_block_transactions_ext(self, block: BlockIdExt, count: int = 256) -> typing.List[Transaction]:
        mode = 39  # 100111
        data = {'id': block.to_dict(), 'mode': mode, 'count': count, 'want_proof': b''}
        result = await self.liteserver_request('listBlockTransactionsExt', data)

        transactions_cells = Cell.from_boc(result['transactions'])
        if not result['transactions']:
            return []
        if self.trust_level <= 1:
            proof = Cell.one_from_boc(result['proof'])
            check_block_header_proof(proof[0], block.root_hash)
            acc_block = Block.deserialize(proof[0].begin_parse()).extra.account_blocks[0]
            if not self.trust_level and block != self.last_mc_block:
                await self.prove_block(block)
        tr_result = []

        for tr_root in transactions_cells:
            transaction = Transaction.deserialize(tr_root.begin_parse())
            if self.trust_level <= 1:
                prunned_tr_cell = acc_block.get(int(transaction.account_addr, 16)).transactions[0].get(transaction.lt)
                assert prunned_tr_cell.get_hash(0) == tr_root.get_hash(0)
            # transaction.account = Address((block.workchain, bytes.fromhex(transaction.account_addr)))
            tr_result.append(transaction)

        return tr_result

    async def raw_get_mc_block_proof(self, known_block: BlockIdExt, target_block: typing.Optional[BlockIdExt] = None, return_best_key_block=False) -> typing.Tuple[bool, BlockIdExt, typing.Optional[BlockIdExt], typing.Optional[int]]:
        """
        :param known_block: block you trust
        :param target_block: block you want to prove
        :param return_best_key_block: if true the key block with big ttl will be returned
        :return: (bool, BlockIdExt, BlockIdExt, int) - is completed proof, last trusted block, best key block (see documentation), and best key block gen_utime
        """
        mode = 0

        if target_block:
            mode = 1  # 1
        data = {'known_block': known_block.to_dict(), 'mode': mode, 'target_block': target_block.to_dict()}
        result = await self.liteserver_request('getBlockProof', data)
        last_trusted = known_block
        best_key = None
        best_key_ts = 0
        for step in result['steps']:
            if 'config_proof' in step:  # blockLinkForward
                assert last_trusted == BlockIdExt.from_dict(step['from'])
                to_block = BlockIdExt.from_dict(step['to'])

                dest_proof = Cell.one_from_boc(step['dest_proof'])
                config_proof = Cell.one_from_boc(step['config_proof'])
                check_block_header_proof(dest_proof[0], to_block.root_hash)

                block = Block.deserialize(config_proof[0].begin_parse())
                dest_block = Block.deserialize(dest_proof[0].begin_parse())
                if self.last_key_block is None or block.info.seqno > self.last_key_block.seqno:
                    self.last_key_block = last_trusted
                if step['to_key_block']:
                    if self.last_key_block is None or dest_block.info.seqno > self.last_key_block.seqno:
                        self.last_key_block = to_block
                if return_best_key_block:
                    best_key, best_key_ts = choose_key_block(best_key, best_key_ts, last_trusted, block.info.gen_utime)
                    if step['to_key_block']:
                        best_key, best_key_ts = choose_key_block(best_key, best_key_ts, to_block, dest_block.info.gen_utime)

                param_34 = ConfigParam34.deserialize(block.extra.custom.config.config[34])
                param_28 = ConfigParam28.deserialize(block.extra.custom.config.config[28])

                nodes = compute_validator_set(param_28, to_block, param_34.cur_validators)
                check_block_signatures(nodes=nodes, signatures=step['signatures']['signatures'], blk=to_block)
                last_trusted = to_block

            else:  # blockLinkBack
                assert last_trusted == BlockIdExt.from_dict(step['from'])
                to_block = BlockIdExt.from_dict(step['to'])
                if step['to_key_block']:
                    dest_proof = Cell.one_from_boc(step['dest_proof'])
                    state_proof = Cell.one_from_boc(step['state_proof'])
                    proof = Cell.one_from_boc(step['proof'])
                    block = Block.deserialize(proof[0].begin_parse())
                    if return_best_key_block:
                        best_key, best_key_ts = choose_key_block(best_key, best_key_ts, to_block, block.info.gen_utime)
                    state_hash = check_block_header_proof(proof[0], last_trusted.root_hash, True)
                    assert state_hash == state_proof[0].get_hash(0)

                    state = ShardStateUnsplit.deserialize(state_proof[0].begin_parse())
                    last_key = state.custom.last_key_block
                    check_block_header_proof(dest_proof[0], last_key.root_hash)
                    assert to_block.root_hash == last_key.root_hash
                    if self.last_key_block is None or to_block.seqno > self.last_key_block.seqno:
                        self.last_key_block = to_block
                    last_trusted = to_block
                else:
                    dest_proof = Cell.one_from_boc(step['dest_proof'])  # ?
                    state_proof = Cell.one_from_boc(step['state_proof'])
                    proof = Cell.one_from_boc(step['proof'])

                    state_hash = check_block_header_proof(proof[0], last_trusted.root_hash, True)
                    assert state_hash == state_proof[0].get_hash(0)
                    state = ShardStateUnsplit.deserialize(state_proof[0].begin_parse())
                    blk = state.custom.prev_blocks[0].get(to_block.seqno)
                    if not blk:
                        raise LiteClientError(f'cannot find {to_block} in OldMcBlocksInfo')
                    blk: KeyExtBlkRef

                    assert blk.blk_ref.root_hash == to_block.root_hash
                    last_trusted = to_block
        return last_trusted == target_block, last_trusted, best_key, best_key_ts

    async def get_mc_block_proof(self, known_block: BlockIdExt, target_block: BlockIdExt, return_best_key_block=False):
        self.logger.debug(msg=f'PROOF BLOCKS\nfrom: {known_block}\ntarget: {target_block}')
        last_proved = known_block
        best_key = None
        best_key_ts = 0
        while last_proved != target_block:
            _, last_proved, key, key_ts = await self.raw_get_mc_block_proof(last_proved, target_block, return_best_key_block)
            if return_best_key_block:
                best_key, best_key_ts = choose_key_block(best_key, best_key_ts, key, key_ts)
            self.logger.debug(msg=f'PROOF BLOCKS\nproved: {last_proved}')
        if return_best_key_block:
            return best_key, best_key_ts

    async def prove_block(self, target_block: BlockIdExt):
        if target_block.workchain == -1:
            await self.get_mc_block_proof(self.last_key_block, target_block)
        else:
            await self.get_shard_block_proof(target_block, True)

    def unpack_config(self, block: BlockIdExt, config_proof: Cell, state_proof: Cell):
        if self.trust_level <= 1:
            state_hash = check_block_header_proof(state_proof[0], block.root_hash, True)
            if config_proof[0].get_hash(0) != state_hash:
                raise LiteClientError('hashes mismach')
        shard = ShardStateUnsplit.deserialize(config_proof[0].begin_parse())
        config = shard.custom.config.config
        config_res = {}
        for i, v in config.items():
            if i in ConfigParam.params:
                config_res[i] = ConfigParam.params[i].deserialize(v)
            else:
                config_res[i] = v

        return config_res

    async def get_config_all(self, blk: typing.Optional[BlockIdExt] = None):
        trusted = False
        if blk is None:
            blk = self.last_mc_block
            trusted = True

        mode = 0  # ?

        data = {'mode': mode, 'id': blk.to_dict()}

        result = await self.liteserver_request('getConfigAll', data)

        if not self.trust_level and not trusted:
            await self.prove_block(blk)

        config_proof = Cell.one_from_boc(result['config_proof'])
        state_proof = Cell.one_from_boc(result['state_proof'])
        return self.unpack_config(blk, config_proof, state_proof)

    async def get_config_params(self, params: typing.List[int], blk: typing.Optional[BlockIdExt] = None):
        trusted = False
        if blk is None:
            blk = self.last_mc_block
            trusted = True

        mode = 0  # ?
        data = {'mode': mode, 'id': blk.to_dict(), 'param_list': params}
        result = await self.liteserver_request('getConfigParams', data)

        if not self.trust_level and not trusted:
            await self.prove_block(blk)

        config_proof = Cell.one_from_boc(result['config_proof'])
        state_proof = Cell.one_from_boc(result['state_proof'])
        return self.unpack_config(blk, config_proof, state_proof)

    async def get_libraries(self, library_list: typing.List[bytes]):
        data = {'library_list': library_list}

        result = await self.liteserver_request('getLibraries', data)

        return result['result']

    async def get_shard_block_proof(self, blk: BlockIdExt, prove_mc: bool = False):
        data = {'id': blk.to_dict()}

        result = await self.liteserver_request('getShardBlockProof', data)
        mc_block = BlockIdExt.from_dict(result['masterchain_id'])

        if prove_mc:
            await self.get_mc_block_proof(known_block=self.last_key_block, target_block=mc_block)

        for link in result['links']:
            if BlockIdExt.from_dict(link['id']) == blk:
                proof = Cell.one_from_boc(link['proof'])
                check_block_header_proof(proof[0], mc_block.root_hash)
                shard = Block.deserialize(proof[0].begin_parse()).extra.custom.shard_hashes[blk.workchain].list[0].__dict__
                shardblk = BlockIdExt.from_dict(shard)
                shardblk.seqno = shard['seq_no']
                shardblk.workchain = blk.workchain
                assert shardblk == blk
            else:
                raise NotImplementedError()

    async def raw_send_message(self, message: bytes):
        data = {'body': message}

        result = await self.liteserver_request('sendMessage', data)
        return result['status']

    @classmethod
    def from_config(cls, config: dict, ls_i: int = 0, trust_level: int = 2):
        ls = config['liteservers'][ls_i]
        init_block = config['validator']['init_block']
        init_block['file_hash'] = base64.b64decode(init_block['file_hash']).hex()
        init_block['root_hash'] = base64.b64decode(init_block['root_hash']).hex()
        init_block = BlockIdExt.from_dict(init_block)
        if not trust_level and init_block != init_mainnet_block and init_block != init_testnet_block:
            logging.getLogger(cls.__name__).warning(msg='unknown init block found! please, check its hash to trust it')

        return cls(
            host=socket.inet_ntoa(struct.pack('>i', ls['ip'])),
            port=ls['port'],
            server_pub_key=ls['id']['key'],
            trust_level=trust_level,
            init_key_block=init_block
        )

    @classmethod
    def from_mainnet_config(cls, ls_i: int = 0, trust_level: int = 0):
        config = requests.get('https://ton.org/global-config.json').json()
        return cls.from_config(config, ls_i, trust_level)

    @classmethod
    def from_testnet_config(cls, ls_i: int = 0, trust_level: int = 0):
        config = requests.get('https://ton.org/testnet-global.config.json').json()
        return cls.from_config(config, ls_i, trust_level)
