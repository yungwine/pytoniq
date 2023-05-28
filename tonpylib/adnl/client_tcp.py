import base64
import hashlib
import socket
import asyncio
import typing
from queue import Queue

# from .crypto import ed25519Public, ed25519Private, x25519Public, x25519Private
from .crypto import Server, Client, get_random, create_aes_ctr_cipher, aes_ctr_encrypt, aes_ctr_decrypt, get_shared_key


class AdnlClientTcp:

    def __init__(self,
                 host: str,  # ipv4 host
                 port: int,
                 server_pub_key: str,  # server ed25519 public key in base64,
                 client_private_key: typing.Optional[bytes] = None  # can specify private key, then it's won't be generated
                 ) -> None:
        self.server = Server(host, port, base64.b64decode(server_pub_key))
        if client_private_key is None:
            self.client = Client(Client.generate_ed25519_private_key())  # recommended
        else:
            self.client = Client(client_private_key)

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.reader: asyncio.StreamReader = None  # asyncio StreamReader
        self.writer: asyncio.StreamWriter = None  # asyncio StreamWriter
        self.queue = Queue()
        self.loop = asyncio.get_event_loop()
        self.delta = 0.1

        self.enc_sipher = None
        self.dec_sipher = None

    def encrypt(self, data: bytes) -> bytes:
        return aes_ctr_encrypt(self.enc_sipher, data)

    def decrypt(self, data: bytes) -> bytes:
        return aes_ctr_decrypt(self.dec_sipher, data)

    async def send(self, data: bytes):
        future = self.loop.create_future()
        self.writer.write(data)
        self.queue.put(future)
        await self.writer.drain()
        return future

    async def receive(self, data_len: int) -> bytes:
        data = await self.reader.read(data_len)
        return data

    async def listen(self) -> None:
        while True:
            if self.queue.qsize() == 0:
                await asyncio.sleep(self.delta)
                continue

            for _ in range(self.queue.qsize()):
                data_len_encrypted = await self.receive(4)
                data_len = int(self.decrypt(data_len_encrypted)[::-1].hex(), 16)
                data_encrypted = await self.receive(data_len)
                data = self.decrypt(data_encrypted)
                print('recieved', data)
                self.queue.get().set_result(data)

    async def connect(self) -> None:
        handshake = self.handshake()
        self.reader, self.writer = await asyncio.open_connection(self.server.host, self.server.port)
        future = await self.send(handshake)
        asyncio.create_task(self.listen())
        asyncio.create_task(self.ping())
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

    def get_ping_query(self):
        data = 0x4c.to_bytes(byteorder='little', length=4)  # length
        nonce = get_random(32)
        data += nonce
        data += 0x4d082b9a.to_bytes(byteorder='little', length=4)  # TL id
        query_id = get_random(8)
        data += query_id[::-1]
        hash = hashlib.sha256(data[4:]).digest()  # checksum
        data += hash
        ping_result = self.encrypt(data)
        return ping_result, query_id

    @staticmethod
    def parse_pong(data: bytes, query_id):
        assert data[32:36][::-1].hex() == 'dc69fb03'
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

