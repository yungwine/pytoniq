import base64
import hashlib
import os
import socket
import asyncio
import sys
import time
import typing
from queue import Queue

from ..boc import Slice, Cell
from ..boc.address import Address
# from .crypto import ed25519Public, ed25519Private, x25519Public, x25519Private
from ..crypto.ciphers import Server, Client, get_random, create_aes_ctr_cipher, aes_ctr_encrypt, aes_ctr_decrypt, get_shared_key
from ..crypto.crc import crc16

from ..tl.generator import TlGenerator, TlSchema, TlSchemas
from ..tlb.vm_stack import VmStack


class LiteClientError(BaseException):
    pass

class RunGetMethodError(LiteClientError):
    pass


class AdnlClientTcp:

    def __init__(self,
                 host: str,  # ipv4 host
                 port: int,
                 server_pub_key: str,  # server ed25519 public key in base64,
                 client_private_key: typing.Optional[bytes] = None,
                 # can specify private key, then it's won't be generated
                 schemas_path: typing.Optional[str] = None
                 ) -> None:
        self.tasks = {}
        self.inited = False

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
        self.loop = asyncio.get_event_loop()
        self.delta = 0.1  # listen delay

        """########### TL ###########"""
        if schemas_path is None:
            schemas_path = os.path.join(os.path.dirname(__file__), os.pardir, 'tl/schemas')
        self.schemas = TlGenerator(schemas_path).generate()
        # print(self.schemas)
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
        # self.queue.put(future)
        self.tasks[qid] = future
        return future

    async def send_and_wait(self, data: bytes):
        future = self.loop.create_future()
        self.writer.write(data)
        await self.writer.drain()
        self.queue.put(future)
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
        self.pinger = asyncio.create_task(self.ping(), name='pinger')
        await future
        self.inited = True

    async def close(self) -> None:
        for i in asyncio.all_tasks(self.loop):
            if i.get_name() in ('pinger', 'listener'):
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
        schema = self.schemas.get_by_name('liteServer.' + tl_schema_name)
        data, qid = self.serialize_adnl_ls_query(schema, data)
        data = self.serialize_packet(data)
        resp = await self.send_and_encrypt(data, qid)
        await resp
        return resp.result()

    async def get_masterchain_info(self):
        return await self.liteserver_request('getMasterchainInfo', {})

    async def lookup_block(self, wc: int, shard: int, seqno: int = -1,
                           lt: typing.Optional[int] = None, utime: typing.Optional[int] = None):
        mode = 0
        if seqno != -1:
            mode = 1
        if lt is not None:
            mode = 2
        if utime is not None:
            mode = 4

        data = {'mode': mode, 'id': {'workchain': wc, 'shard': shard, 'seqno': seqno}, 'lt': lt, 'utime': utime}

        return await self.liteserver_request('lookupBlock', data)

    async def get_block(self, wc: int, shard: int, seqno: int):
        # data = {'id': {'workchain': -1, 'shard': -9223372036854775808, 'seqno': 30528305, 'root_hash': '7c06f2fab30f6bbd77820213666184c9b958e1bd1defac1f70cd4893c199e356', 'file_hash': '92f943cf73caec5ecb8ab66fb118eea3eb3ee97c1a49f310ac28415a0a889d0d'}}
        data = {'id': {'workchain': -1, 'shard': -9223372036854775808, 'seqno': 30528401, 'root_hash': 'b0c09b7c116f951092b3d1b258fb98adc01c698a227b3b2e268469c24173eeb2', 'file_hash': '90a3ece36fee00c4d4e74cf0c2cdfc87667ec6b1973c0b6d212c3a83eaf2dcac'}}
        return await self.liteserver_request('getBlock', data)

    async def run_get_method(self, address: typing.Union[Address, str], method: typing.Union[int, str], stack: list):

        mode = 7  # 111

        block = (await self.get_masterchain_info())['last']  # take from cache TODO

        account = {}

        if isinstance(address, str):
            address = Address(address)

        if isinstance(address, Address):
            account['workchain'] = address.wc
            account['id'] = address.hash_part.hex()
        else:
            raise LiteClientError('provided address in unknown form')
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

        data = {'mode': mode, 'id': block, 'account': account, 'method_id': method_id, 'params': stack.to_boc()}

        result = await self.liteserver_request('runSmcMethod', data)

        if result['exit_code'] != 0:
            raise RunGetMethodError(f'get method "{method}" for account {address} returned exit code {result["exit_code"]}')

        # print(Cell.one_from_boc(result['state_proof']))
        # print(result['shard_proof'].hex())
        # print(result['proof'])
        # print(result['result'])
        print('exit code', result['exit_code'])
        return VmStack.deserialize(Slice.one_from_boc(result['result']))
