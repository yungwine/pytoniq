import base64
import hashlib
import logging
import os
import socket
import asyncio
import sys
import time
import typing
from queue import Queue

from ..boc import Slice, Cell
from ..boc.exotic import check_block_header_proof, check_shard_proof, check_account_proof, check_proof
from ..boc.address import Address

# from .crypto import ed25519Public, ed25519Private, x25519Public, x25519Private
from ..crypto.ciphers import Server, Client, get_random, create_aes_ctr_cipher, aes_ctr_encrypt, aes_ctr_decrypt, get_shared_key
from ..crypto.crc import crc16

from ..tl.generator import TlGenerator, TlSchema, TlSchemas
from ..tl.block import BlockId, BlockIdExt
from ..tlb.transaction import Transaction
from ..tlb.utils import deserialize_shard_hashes

from ..tlb.vm_stack import VmStack
from ..tlb.block import Block, ShardDescr, BinTree, ShardStateUnsplit
from ..tlb.account import Account, SimpleAccount, ShardAccount, AccountBlock


class LiteClientError(BaseException):
    pass


class RunGetMethodError(LiteClientError):
    pass


class AdnlClientTcp:

    def __init__(self,
                 host: str,  # ipv4 host
                 port: int,
                 server_pub_key: str,  # server ed25519 public key in base64,
                 client_private_key: typing.Optional[bytes] = None,  # can specify private key, then it's won't be generated
                 tl_schemas_path: typing.Optional[str] = None,
                 ) -> None:

        """########### init ###########"""
        self.tasks = {}
        self.inited = False
        self.last_mc_block: BlockIdExt = None
        self.last_shard_blocks: typing.Dict[int, BlockIdExt] = None

        """########### crypto ###########"""
        self.server = Server(host, port, base64.b64decode(server_pub_key))
        if client_private_key is None:
            self.client = Client(Client.generate_ed25519_private_key())  # recommended
        else:
            self.client = Client(client_private_key)
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

    async def send_and_wait(self, data: bytes, qid: typing.Union[str, int, None]) -> dict:
        future = self.loop.create_future()
        self.writer.write(data)
        await self.writer.drain()
        self.tasks[qid] = future
        await future
        return future.result()

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
        data = self.decrypt(await self.reader.read(data_len))
        return data

    async def listen(self) -> None:
        while True:
            while not self.tasks:
                await asyncio.sleep(self.delta)

            data_len_encrypted = await self.receive(4)
            data_len = int(self.decrypt(data_len_encrypted)[::-1].hex(), 16)
            data_encrypted = await self.receive(data_len)
            data_decrypted = self.decrypt(data_encrypted)
            # check hashsum
            assert hashlib.sha256(data_decrypted[:-32]).digest() == data_decrypted[-32:], 'incorrect checksum'
            result = self.deserialize_adnl_query(data_decrypted[:-32])
            if not result:
                # for handshake
                result = {}
            qid = result.get('query_id', result.get('random_id'))

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
            print('passed!')

    async def liteserver_request(self, tl_schema_name: str, data: dict) -> dict:
        # while not self.inited:
        #     await asyncio.sleep(0)
        schema = self.schemas.get_by_name('liteServer.' + tl_schema_name)
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

    async def update_last_blocks(self):
        self.last_mc_block = BlockIdExt.from_dict((await self.get_masterchain_info())['last'])
        shards = await self.raw_get_all_shards_info(self.last_mc_block)
        shard_result = {}
        for k, v in shards.items():
            shard: ShardDescr = v.list[0]
            shard_result[k] = BlockIdExt(workchain=k, seqno=shard.seq_no, shard=None, root_hash=shard.root_hash,
                                         file_hash=shard.file_hash)
        self.last_shard_blocks = shard_result
        print('updated!', self.last_mc_block, self.last_shard_blocks)

    async def block_updater(self):
        if self.last_mc_block is None:
            self.last_mc_block = BlockIdExt.from_dict((await self.get_masterchain_info())['last'])
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
        result = await self.liteserver_request('getBlockHeader', block.to_dict() | {'mode': 0})
        h_proof = Cell.one_from_boc(result['header_proof'])
        check_block_header_proof(h_proof[0], bytes.fromhex(result['id']['root_hash']))
        return Block.deserialize(h_proof[0].begin_parse())

    async def get_block_header(self, wc: int, shard: typing.Optional[int], seqno: int, root_hash: typing.Union[str, bytes], file_hash: typing.Union[str, bytes]):
        block = self.pack_block_id_ext(wc=wc, shard=shard, seqno=seqno, root_hash=root_hash, file_hash=file_hash)
        result = await self.liteserver_request('getBlockHeader', block | {'mode': 0})
        h_proof = Cell.one_from_boc(result['header_proof'])
        check_block_header_proof(h_proof[0], bytes.fromhex(result['id']['root_hash']))
        return Block.deserialize(h_proof[0].begin_parse())

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

        check_block_header_proof(h_proof[0], bytes.fromhex(result['id']['root_hash']))

        return BlockIdExt.from_dict(result['id']), Block.deserialize(h_proof[0].begin_parse())

    async def raw_get_block(self, block: BlockIdExt):
        result = await self.liteserver_request('getBlock', {'id': block.to_dict()})
        result_block = Cell.one_from_boc(result['data'])
        check_block_header_proof(result_block, block_hash=block.root_hash)
        return Block.deserialize(Slice.one_from_boc(result['data']))

    async def get_block(self, wc: int, shard: typing.Optional[int], seqno: int, root_hash: typing.Union[str, bytes], file_hash: typing.Union[str, bytes]):
        block = self.pack_block_id_ext(wc=wc, shard=shard, seqno=seqno, root_hash=root_hash, file_hash=file_hash)
        result = await self.liteserver_request('getBlock', block)
        result_block = Cell.one_from_boc(result['data'])
        check_block_header_proof(result_block, block_hash=bytes.fromhex(block['id']['root_hash']))
        return Block.deserialize(Slice.one_from_boc(result['data']))

    async def raw_get_account_state(self, address: typing.Union[str, Address]) -> typing.Tuple[Account, ShardAccount]:
        block = self.last_mc_block

        if isinstance(address, str):
            address = Address(address)

        account = address.to_tl_account_id()

        data = {'id': block.to_dict(), 'account': account}

        result = await self.liteserver_request('getAccountState', data)

        shrd_blk = BlockIdExt.from_dict(result['shardblk'])
        account_state_root = Cell.one_from_boc(result['state'])

        # check_block_header_proof(result['proof'], bytes.fromhex(result['shardblk']['root_hash']))

        check_shard_proof(shard_proof=result['shard_proof'], blk=block, shrd_blk=shrd_blk)

        shard_account = check_account_proof(proof=result['proof'], shrd_blk=shrd_blk, address=address, account_state_root=account_state_root, return_account_descr=True)

        return Account.deserialize(account_state_root.begin_parse()), shard_account

    async def get_account_state(self, address: typing.Union[str, Address]) -> SimpleAccount:
        return SimpleAccount.from_raw((await self.raw_get_account_state(address))[0])

    async def run_get_method(self, address: typing.Union[Address, str], method: typing.Union[int, str], stack: list):

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

        shrd_blk = BlockIdExt.from_dict(result['shardblk'])
        check_shard_proof(shard_proof=result['shard_proof'], blk=block, shrd_blk=shrd_blk)

        return VmStack.deserialize(Slice.one_from_boc(result['result']))

    async def raw_get_shard_info(self, block: BlockIdExt, wc: int, shard: int, exact: bool):
        data = {'id': block.to_dict(), 'workchain': wc, 'shard': shard, 'exact': exact}

        result = await self.liteserver_request('getShardInfo', data)

        shrd_blk = BlockIdExt.from_dict(result['shardblk'])
        print(result['shard_descr'])
        check_shard_proof(shard_proof=result['shard_proof'], blk=block, shrd_blk=shrd_blk)

        bin_tree = BinTree.deserialize(Slice.one_from_boc(result['shard_descr']))

        return ShardDescr.deserialize(bin_tree.list[0])

    async def raw_get_all_shards_info(self, block: BlockIdExt) -> typing.Dict[int, BinTree]:
        """
        :param block: blockIdExt
        :return: dict[workchain: BinTree[ShardDescr]]
        """
        data = {'id': block.to_dict()}

        result = await self.liteserver_request('getAllShardsInfo', data)

        proof_cells = Cell.from_boc(result['proof'])

        state_hash = check_block_header_proof(proof_cells[0][0], block_hash=block.root_hash, store_state_hash=True)

        check_proof(proof_cells[1], state_hash)

        shard_state = ShardStateUnsplit.deserialize(proof_cells[1][0].begin_parse())

        assert shard_state.shard_id.workchain_id == block.workchain
        assert shard_state.seq_no == block.seqno

        shard_hashes_cell = Cell.one_from_boc(result['data'])
        assert shard_hashes_cell[0].get_hash(0) == proof_cells[1][0][3][0].get_hash(0)  # masterchain_state_extra -> shard_hashes

        return deserialize_shard_hashes(shard_hashes_cell.begin_parse())

    async def get_one_transaction(self, address: typing.Union[Address, str], lt: int, block: typing.Optional[BlockIdExt] = None) -> typing.Optional[Transaction]:
        if isinstance(address, str):
            address = Address(address)

        if block is None:
            if address.wc == -1:
                block = self.last_mc_block
            else:
                block = self.last_shard_blocks[address.wc]

        data = {'id': block.to_dict(), 'account': address.to_tl_account_id(), 'lt': lt}

        result = await self.liteserver_request('getOneTransaction', data)

        if not result['transaction']:
            return None

        transaction_root = Cell.one_from_boc(result['transaction'])

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

    async def raw_get_transactions(self, address: typing.Union[Address, str], count: int, from_lt: int = None, from_hash: typing.Optional[bytes] = None) -> typing.Optional[Transaction]:
        if isinstance(address, str):
            address = Address(address)

        if not from_lt or not from_hash:
            state, shard_account = await self.raw_get_account_state(address)
            from_lt, from_hash = shard_account.last_trans_lt, shard_account.last_trans_hash

        data = {'count': count, 'account': address.to_tl_account_id(), 'lt': from_lt, 'hash': from_hash.hex()}

        result = await self.liteserver_request('getTransactions', data)

        transactions_cells = Cell.from_boc(result['transactions'])

        print(result)
