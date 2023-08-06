import asyncio
import base64
import os
import socket
import time
import hashlib
import typing
from asyncio import transports
from typing import Any

from nacl.signing import SigningKey
from pytoniq_core.tl.generator import TlGenerator, TlSchema
from pytoniq_core.tl.block import BlockId, BlockIdExt

from pytoniq_core.crypto.ciphers import Server, Client, AdnlChannel, get_random, create_aes_ctr_cipher, aes_ctr_encrypt, aes_ctr_decrypt, get_shared_key, create_aes_ctr_sipher_from_key_n_data
from pytoniq_core.crypto.crc import crc16
from pytoniq_core.crypto.signature import sign_message


class AdnlUdpClientError(Exception):
    pass


class SocketProtocol(asyncio.DatagramProtocol):

    def __init__(self):
        # https://github.com/eerimoq/asyncudp/blob/main/asyncudp/__init__.py
        self._error = None
        self._packets = asyncio.Queue(10)

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
        return await self._packets.get()


class AdnlUdpClient:

    def __init__(self,
                 host: str,
                 port: int,
                 server_pub_key: str,  # server ed25519 public key in base64,
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
        self.requests = {}  # dict {seqno[int]: response[dict]}

        """########### connection ###########"""
        self.host = host
        self.port = port
        self.transport: asyncio.Transport = None
        self.protocol: asyncio.Protocol = None
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

    async def send_message_in_channel(self, data: dict, channel: typing.Optional[AdnlChannel] = None) -> dict:
        if channel is None:
            if not self.channels:
                raise AdnlUdpClientError('no channels created!')
            channel = self.channels[0]

        data = self.prepare_packet_content_msg(data)
        sending_seqno = data.get('seqno')

        if self.seqno == sending_seqno:
            self.seqno += 1
        else:
            raise Exception(f'sending seqno {sending_seqno}, client seqno: {self.seqno}')
        serialized = self.schemas.serialize(self.adnl_packet_content_sch, data)
        res = channel.encrypt(serialized)

        self.transport.sendto(res, None)
        packet, port = await self.protocol.receive()

        checksum = packet[32:64]
        encrypted = packet[64:]
        decrypted = channel.decrypt(encrypted, checksum)

        response = self.schemas.deserialize(decrypted)[0]

        self.requests[response.get('seqno')] = response
        received_confirm_seqno = response.get('confirm_seqno')

        if received_confirm_seqno > self.confirm_seqno:
            self.confirm_seqno = received_confirm_seqno

        while sending_seqno not in self.requests:
            # if method got not its seqno than it adds received response to the `requests` dict and waits until some other method got its response
            await asyncio.sleep(0)
        return self.requests.pop(sending_seqno)

    async def send_message_outside_channel(self, data: dict) -> dict:
        """
        Serializes, signs and encrypts sending message.
        :param data: data for `adnl.packetContents` TL Scheme
        :return: decrypted and deserialized response
        """
        data = self.prepare_packet_content_msg(data)
        sending_seqno = data.get('seqno')

        data = self.compute_flags_for_packet(data)

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

        packet, port = await self.protocol.receive()

        assert packet[:32] == self.client.get_key_id()

        server_public_key = packet[32:64]
        checksum = packet[64:96]
        encrypted = packet[96:]

        shared_key = get_shared_key(self.client.x25519_private.encode(), Server(self.host, self.port, server_public_key).x25519_public.encode())
        dec_cipher = create_aes_ctr_sipher_from_key_n_data(shared_key, checksum)
        data = aes_ctr_decrypt(dec_cipher, encrypted)
        assert hashlib.sha256(data).digest() == checksum

        response = self.schemas.deserialize(data)[0]
        self.requests[response.get('seqno')] = response
        received_confirm_seqno = response.get('confirm_seqno')

        if received_confirm_seqno > self.confirm_seqno:
            self.confirm_seqno = received_confirm_seqno

        while sending_seqno not in self.requests:
            # if method got not its seqno than it adds received response to the `requests` dict and waits until some other method got its response
            await asyncio.sleep(0)
        return self.requests.pop(sending_seqno)

    async def connect(self) -> dict:
        """
        Connects to the peer, creates channel and asks for a signed list in channel.
        :return: response dict for dht.getSignedAddressList
        """
        self.loop = asyncio.get_running_loop()
        self.transport, self.protocol = await self.loop.create_datagram_endpoint(SocketProtocol, remote_addr=(self.host, self.port))

        ts = int(time.time())
        channel_client = Client(Client.generate_ed25519_private_key())
        create_channel_message = self.schemas.serialize(schema=self.create_channel_sch, data={'key': channel_client.ed25519_public.encode().hex(), 'date': ts})

        get_addr_list_message = self.schemas.serialize(
            self.adnl_query_sch,
            data={
                    'query_id': get_random(32),
                    'query': self.schemas.get_by_name('dht.getSignedAddressList').little_id()
            }
        )

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

        data = await self.send_message_outside_channel(data)
        messages = data['messages']

        confirm_channel = messages[0]
        assert confirm_channel.get('type') == 'adnl.message.confirmChannel', f'expected adnl.message.confirmChannel, got {confirm_channel.get("type")}'
        assert confirm_channel['peer_key'] == channel_client.ed25519_public.encode().hex()

        channel_server = Server(self.host, self.port, bytes.fromhex(confirm_channel['key']))

        channel = AdnlChannel(channel_client, channel_server, self.local_id, self.peer_id)

        self.channels.append(channel)

        # test channel:

        data = {
            'message': get_addr_list_message,
        }

        result = await self.send_message_in_channel(data)
        return result['message']['answer']

    async def send_query_message(self, tl_schema_name: str, data: dict) -> dict:
        message = self.schemas.serialize(
            self.adnl_query_sch,
            data={
                'query_id': get_random(32),
                'query': self.schemas.serialize(
                    self.schemas.get_by_name(tl_schema_name),
                    data
                )
            }
        )

        data = {
            'message': message,
        }

        result = await self.send_message_in_channel(data)
        return result['message']['answer']

    async def get_signed_address_list(self) -> dict:
        return await self.send_query_message('dht.getSignedAddressList', {})

    async def send_custom_message(self, message: bytes) -> dict:
        # TODO test
        custom_message = self.schemas.serialize(
            self.schemas.get_by_name('adnl.message.custom'),
            data={
                'data': message
            }
        )

        data = {
            'message': custom_message,
        }

        result = await self.send_message_in_channel(data)
        return result['message']['answer']
