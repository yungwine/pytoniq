import asyncio
import base64
import socket
import struct
import time
import hashlib
import typing
from asyncio import transports
from typing import Any

from pytoniq_core.tl.generator import TlGenerator

from pytoniq_core.crypto.ciphers import Server, Client, AdnlChannel, get_random, aes_ctr_encrypt, aes_ctr_decrypt, get_shared_key, create_aes_ctr_sipher_from_key_n_data
from pytoniq_core.crypto.signature import verify_sign


class AdnlUdpClientError(Exception):
    pass


class SocketProtocol(asyncio.DatagramProtocol):

    def __init__(self, timeout: int = 10):
        # https://github.com/eerimoq/asyncudp/blob/main/asyncudp/__init__.py
        self._error = None
        self._packets = asyncio.Queue(1000)
        self.timeout = timeout

    def connection_made(self, transport: transports.DatagramTransport) -> None:
        print('connected')
        super().connection_made(transport)

    def datagram_received(self, data: bytes, addr: tuple[str | Any, int]) -> None:
        print('received', data)
        self._packets.put_nowait((data, addr))
        super().datagram_received(data, addr)

    def error_received(self, exc: Exception) -> None:
        print('error')
        raise exc
        super().error_received(exc)

    async def receive(self):
        return await asyncio.wait_for(self._packets.get(), self.timeout)  # TODO improve timeout


class AdnlUdpClient:

    def __init__(self,
                 host: str,
                 port: int,
                 server_pub_key: str,  # server ed25519 public key in base64,
                 timeout: int = 3,
                 tl_schemas_path: typing.Optional[str] = None,
                 ) -> None:
        """
        ADNL over UDP client
        :param host: peer host
        :param port: peer port
        :param server_pub_key: peer public key in b64
        :param tl_schemas_path: path to custom TL schemes if needed
        """

        """########### init ###########"""
        self.loop: asyncio.AbstractEventLoop = None
        self.timeout = timeout
        self.listener = None
        self.tasks: typing.Dict[str, asyncio.Future] = {}

        """########### connection ###########"""
        self.host = host
        self.port = port
        self.transport: asyncio.Transport = None
        self.protocol: SocketProtocol = None
        self.seqno = 1
        self.confirm_seqno = 0

        """########### TL ###########"""
        if tl_schemas_path is None:
            self.schemas = TlGenerator.with_default_schemas().generate()
        else:
            self.schemas = TlGenerator(tl_schemas_path).generate()
        self.adnl_query_sch = self.schemas.get_by_name('adnl.message.query')
        self.adnl_packet_content_sch = self.schemas.get_by_name('adnl.packetContents')
        self.create_channel_sch = self.schemas.get_by_name('adnl.message.createChannel')

        """########### crypto ###########"""
        self.server = Server(host, port, base64.b64decode(server_pub_key))
        self.client = Client(Client.generate_ed25519_private_key())
        self.local_id = self.client.get_key_id()
        self.peer_id = self.server.get_key_id()
        self.channels: typing.List[AdnlChannel] = []
        self.enc_sipher = None
        self.dec_sipher = None

    @staticmethod
    def _get_rand():
        rand = get_random(16)
        if rand[0] & 1 > 0:
            return rand[1:]
        return rand[1:8]

    @staticmethod
    def compute_flags_for_packet(data: dict) -> dict:
        """
        :param data: dict with TL Scheme arguments
        :return: data with computed flags field
        """
        flags = 0
        if 'from' in data:
            flags += 1 << 0
        if 'from_short' in data:
            flags += 1 << 1
        if 'message' in data:
            flags += 1 << 2
        if 'messages' in data:
            flags += 1 << 3
        if 'address' in data:
            flags += 1 << 4
        if 'priority_address' in data:
            flags += 1 << 5
        if 'seqno' in data:
            flags += 1 << 6
        if 'confirm_seqno' in data:
            flags += 1 << 7
        if 'recv_addr_list_version' in data:
            flags += 1 << 8
        if 'recv_priority_addr_list_version' in data:
            flags += 1 << 9
        if 'reinit_date' in data or 'dst_reinit_date' in data:
            flags += 1 << 10
        if 'signature' in data:
            flags += 1 << 11

        return data | {'flags': flags}

    def prepare_packet_content_msg(self, data: dict) -> dict:
        """
        Adds random bytes, seqno, confirm_seqno and flags in message args if they were not provided
        """
        if 'rand1' not in data or 'rand2' not in data:
            data['rand1'] = self._get_rand()
            data['rand2'] = self._get_rand()

        if data.get('seqno') is None:
            data['seqno'] = self.seqno
        if data.get('confirm_seqno') is None:
            data['confirm_seqno'] = self.confirm_seqno

        return self.compute_flags_for_packet(data)

    def _decrypt_any(self, resp_packet: bytes) -> bytes:
        key_id = resp_packet[:32]
        if key_id == self.client.get_key_id():
            server_public_key = resp_packet[32:64]
            checksum = resp_packet[64:96]
            encrypted = resp_packet[96:]

            shared_key = get_shared_key(self.client.x25519_private.encode(),
                                        Server(self.host, self.port, server_public_key).x25519_public.encode())
            dec_cipher = create_aes_ctr_sipher_from_key_n_data(shared_key, checksum)
            decrypted = aes_ctr_decrypt(dec_cipher, encrypted)
            assert hashlib.sha256(decrypted).digest() == checksum, 'invalid checksum'
            return decrypted
        else:
            for channel in self.channels:
                if key_id == channel.server_aes_key_id:
                    checksum = resp_packet[32:64]
                    encrypted = resp_packet[64:]
                    decrypted = channel.decrypt(encrypted, checksum)
                    assert hashlib.sha256(decrypted).digest() == checksum, 'invalid checksum'
                    return decrypted
            # raise AdnlUdpClientError(f'unknown key id from node: {key_id}')

    def process_outcoming_message(self, message: dict) -> typing.Optional[asyncio.Future]:
        future = self.loop.create_future()
        type_ = message['@type']
        if type_ == 'adnl.message.query':
            self.tasks[message.get('query_id')[::-1].hex()] = future
        elif type_ == 'adnl.message.createChannel':
            self.tasks[message.get('key')] = future
        else:
            raise AdnlUdpClientError(f'unexpected message sending as a client: {message}')
        return future

    def _create_futures(self, data: dict) -> typing.List[asyncio.Future]:
        futures = []
        if data.get('message'):
            future = self.process_outcoming_message(data['message'])
            if future is not None:
                futures.append(future)

        if data.get('messages'):
            for message in data['messages']:
                future = self.process_outcoming_message(message)
                if future is not None:
                    futures.append(future)
        return futures

    @staticmethod
    async def _receive(futures: typing.List[asyncio.Future]) -> list:
        return list(await asyncio.gather(*futures))

    def process_incoming_message(self, message: dict):
        if message['@type'] == 'adnl.message.answer':
            future = self.tasks.pop(message.get('query_id'))
            future.set_result(message['answer'])
        elif message['@type'] == 'adnl.message.confirmChannel':
            future = self.tasks.pop(message.get('peer_key'))
            future.set_result(message)
        else:
            raise AdnlUdpClientError(f'unexpected message type received as a client: {message}')

    async def listen(self):
        while True:
            packet, addr = await self.protocol.receive()
            decrypted = self._decrypt_any(packet)
            if decrypted is None:
                continue
            response = self.schemas.deserialize(decrypted)[0]
            received_confirm_seqno = response.get('confirm_seqno')

            if received_confirm_seqno > self.confirm_seqno:
                self.confirm_seqno = received_confirm_seqno

            message = response.get('message')
            messages = response.get('messages')

            if message:
                self.process_incoming_message(message)
            if messages:
                for message in messages:
                    self.process_incoming_message(message)

    async def send_message_in_channel(self, data: dict, channel: typing.Optional[AdnlChannel] = None) -> list:
        if channel is None:
            if not self.channels:
                raise AdnlUdpClientError('no channels created!')
            channel = self.channels[0]

        data = self.prepare_packet_content_msg(data)
        sending_seqno = data.get('seqno')

        futures = self._create_futures(data)

        if self.seqno == sending_seqno:
            self.seqno += 1
        else:
            raise Exception(f'sending seqno {sending_seqno}, client seqno: {self.seqno}')
        serialized = self.schemas.serialize(self.adnl_packet_content_sch, data)
        res = channel.encrypt(serialized)

        self.transport.sendto(res, None)
        result = await asyncio.wait_for(self._receive(futures), self.timeout)

        return result

    async def send_message_outside_channel(self, data: dict) -> list:
        """
        Serializes, signs and encrypts sending message.
        :param data: data for `adnl.packetContents` TL Scheme
        :return: decrypted and deserialized response
        """
        data = self.prepare_packet_content_msg(data)
        sending_seqno = data.get('seqno')

        data = self.compute_flags_for_packet(data)

        futures = self._create_futures(data)

        serialized1 = self.schemas.serialize(self.adnl_packet_content_sch, self.compute_flags_for_packet(data))
        signature = self.client.sign(serialized1)
        serialized2 = self.schemas.serialize(self.adnl_packet_content_sch,
                                             self.compute_flags_for_packet(data | {'signature': signature}))

        checksum = hashlib.sha256(serialized2).digest()
        shared_key = get_shared_key(self.client.x25519_private.encode(), self.server.x25519_public.encode())
        init_cipher = create_aes_ctr_sipher_from_key_n_data(shared_key, checksum)
        data = aes_ctr_encrypt(init_cipher, serialized2)

        res = self.peer_id + self.client.ed25519_public.encode() + checksum + data
        self.transport.sendto(res, None)

        if self.seqno == sending_seqno:
            self.seqno += 1
        else:
            raise Exception(f'sending seqno {sending_seqno}, client seqno: {self.seqno}')

        result = await asyncio.wait_for(self._receive(futures), self.timeout)
        return result

    async def connect(self) -> list:
        """
        Connects to the peer, creates channel and asks for a signed list in channel.
        :return: response dict for dht.getSignedAddressList
        """
        self.loop = asyncio.get_running_loop()
        self.transport, self.protocol = await self.loop.create_datagram_endpoint(lambda: SocketProtocol(timeout=self.timeout), remote_addr=(self.host, self.port))

        ts = int(time.time())
        channel_client = Client(Client.generate_ed25519_private_key())
        create_channel_message = {
            '@type': 'adnl.message.createChannel',
            'key': channel_client.ed25519_public.encode().hex(),
            'date': ts
        }

        get_addr_list_message = {
            '@type': 'adnl.message.query',
            'query_id': get_random(32),
            'query': self.schemas.get_by_name('dht.getSignedAddressList').little_id()
        }

        from_ = self.schemas.serialize(self.schemas.get_by_name('pub.ed25519'), data={'key': self.client.ed25519_public.encode().hex()})
        data = {
            'from': from_,
            'messages': [create_channel_message, get_addr_list_message],
            'address': {
                'addrs': [],
                'version': ts,
                'reinit_date': ts,
                'priority': 0,
                'expire_at': 0,
            },
            'recv_addr_list_version': ts,
            'reinit_date': ts,
            'dst_reinit_date': 0,
        }

        self.listener = self.loop.create_task(self.listen())

        messages = await self.send_message_outside_channel(data)

        confirm_channel = messages[0]
        assert confirm_channel.get('@type') == 'adnl.message.confirmChannel', f'expected adnl.message.confirmChannel, got {confirm_channel.get("@type")}'
        assert confirm_channel['peer_key'] == channel_client.ed25519_public.encode().hex()

        channel_server = Server(self.host, self.port, bytes.fromhex(confirm_channel['key']))

        channel = AdnlChannel(channel_client, channel_server, self.local_id, self.peer_id)

        self.channels.append(channel)

        # test channel:

        data = {
            'message': get_addr_list_message,
        }

        result = await self.send_message_in_channel(data)
        return result

    async def close(self):
        self.transport.close()

    async def send_query_message(self, tl_schema_name: str, data: dict) -> dict:
        message = {
            '@type': 'adnl.message.query',
            'query_id': get_random(32),
            'query': self.schemas.serialize(
                    self.schemas.get_by_name(tl_schema_name),
                    data
            )
        }

        data = {
            'message': message,
        }

        result = await self.send_message_in_channel(data)
        return result

    async def get_signed_address_list(self) -> dict:
        return await self.send_query_message('dht.getSignedAddressList', {})

    async def send_custom_message(self, message: bytes) -> list:
        # TODO test

        custom_message = {
            '@type': 'adnl.message.custom',
            'data': message
        }

        data = {
            'message': custom_message,
        }

        result = await self.send_message_in_channel(data)
        return result

    async def dht_find_value(self, key: bytes, k: int = 6):
        data = {'key': key.hex(), 'k': k}
        return await self.send_query_message('dht.findValue', data)

    @classmethod
    def from_dict(cls, data: dict, timeout: int = 10, check_signature=True) -> "AdnlUdpClient":
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
                raise AdnlUdpClientError('invalid node signature!')

        node_addr = data['addr_list']['addrs'][0]
        host = socket.inet_ntoa(struct.pack('>i', node_addr['ip']))
        return cls(host=host, port=node_addr['port'], server_pub_key=pub_k_b64, timeout=timeout)

    def __hash__(self):  # to store in sets / dicts as keys
        return int.from_bytes(self.peer_id, 'big')
