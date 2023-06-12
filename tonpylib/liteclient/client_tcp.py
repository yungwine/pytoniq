import base64
import hashlib
import os
import socket
import asyncio
import sys
import time
import typing
from queue import Queue

# from .crypto import ed25519Public, ed25519Private, x25519Public, x25519Private
from .crypto import Server, Client, get_random, create_aes_ctr_cipher, aes_ctr_encrypt, aes_ctr_decrypt, get_shared_key

from ..tl.generator import TlGenerator, TlSchema, TlSchemas


class AdnlClientTcp:

    def __init__(self,
                 host: str,  # ipv4 host
                 port: int,
                 server_pub_key: str,  # server ed25519 public key in base64,
                 client_private_key: typing.Optional[bytes] = None,  # can specify private key, then it's won't be generated
                 schemas_path: typing.Optional[str] = None
                 ) -> None:
        self.queue = Queue()

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
        self.loop = asyncio.get_event_loop()
        self.delta = 0.1  # listen delay

        """########### TL ###########"""
        if schemas_path is None:
            schemas_path = os.path.join(os.path.dirname(__file__), os.pardir, 'tl/schemas')
        self.schemas = TlGenerator(schemas_path).generate()
        # for better performance:
        self.ping_sch = self.schemas.get_by_name('tcp.ping')
        self.pong_sch = self.schemas.get_by_name('tcp.pong')
        self.adnl_query_sch = self.schemas.get_by_name('adnl.message.query')
        self.ls_query_sch = self.schemas.get_by_name('liteServer.query')

    def encrypt(self, data: bytes) -> bytes:
        return aes_ctr_encrypt(self.enc_sipher, data)

    def decrypt(self, data: bytes) -> bytes:
        return aes_ctr_decrypt(self.dec_sipher, data)

    async def send(self, data: bytes):
        future = self.loop.create_future()
        self.writer.write(data)
        await self.writer.drain()
        self.queue.put(future)
        return future

    async def send_and_wait(self, data: bytes):
        future = self.loop.create_future()
        self.writer.write(data)
        await self.writer.drain()
        self.queue.put(future)
        await future
        return future.result()

    async def send_and_encrypt(self, data: bytes):
        future = self.loop.create_future()
        self.writer.write(self.encrypt(data))
        await self.writer.drain()
        self.queue.put(future)
        return future

    async def receive(self, data_len: int) -> bytes:
        data = await self.reader.readexactly(data_len)
        return data

    async def receive_and_decrypt(self, data_len: int) -> bytes:
        data = self.decrypt(await self.reader.read(data_len))
        return data

    async def listen(self) -> None:
        while True:
            while self.queue.qsize() == 0:
                await asyncio.sleep(self.delta)
            item = self.queue.get_nowait()

            data_len_encrypted = await self.receive(4)
            data_len = int(self.decrypt(data_len_encrypted)[::-1].hex(), 16)
            data_encrypted = await self.receive(data_len)
            data = self.decrypt(data_encrypted)

            # print('recieved', data_len)

            item.set_result(data)
            # self.queue.task_done()

    async def connect(self) -> None:
        handshake = self.handshake()
        self.reader, self.writer = await asyncio.open_connection(self.server.host, self.server.port)
        future = await self.send(handshake)
        asyncio.create_task(self.listen(), name='listener')
        asyncio.create_task(self.ping(), name='pinger')
        await future
        print('connected!')

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

    def serialize_adnl_ls_query(self, schema: TlSchema, data: dict) -> tuple:
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
        return res, qid

    def get_ping_query(self):
        ping_sch = self.schemas.get_by_name('tcp.ping')
        query_id = get_random(8)
        data = self.schemas.serialize(ping_sch, {'random_id': query_id})
        data = self.serialize_packet(data)
        ping_result = self.encrypt(data)
        return ping_result, query_id

    def parse_pong(self, data: bytes, query_id):
        assert data[32:36] == self.schemas.get_by_name('tcp.pong').little_id()
        assert data[36:44][::-1] == query_id
        checksum = data[44:]
        hash = hashlib.sha256(data[:44]).digest()
        assert checksum == hash

    async def ping(self):
        while True:
            await asyncio.sleep(3)
            ping_query, qid = self.get_ping_query()
            pong = await self.send(ping_query)
            await pong
            self.parse_pong(pong.result(), qid)
            print('passed!')

    async def get_masterchain_info(self):
        master_sch = self.schemas.get_by_name('liteServer.getMasterchainInfo')
        data, qid = self.serialize_adnl_ls_query(master_sch, {})
        data = self.serialize_packet(data)
        info = await self.send_and_encrypt(data)

        await info
        info = info.result()

        assert info[32:36] == self.schemas.get_by_name('adnl.message.answer').little_id()  # TL id
        # TODO change query system, implement query_id
