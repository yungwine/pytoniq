import asyncio
import base64
import logging
import time
import hashlib
import types
import typing
from asyncio import transports
from typing import Any

from pytoniq_core.tl.generator import TlGenerator

from pytoniq_core.crypto.ciphers import Server, Client, AdnlChannel, get_random, aes_ctr_encrypt, aes_ctr_decrypt, get_shared_key, create_aes_ctr_sipher_from_key_n_data


class SocketProtocol(asyncio.DatagramProtocol):

    def __init__(self, timeout: int = 10):
        # https://github.com/eerimoq/asyncudp/blob/main/asyncudp/__init__.py
        self._error = None
        self._packets = asyncio.Queue(1000)
        self.timeout = timeout
        self.logger = logging.getLogger(self.__class__.__name__)

    def connection_made(self, transport: transports.DatagramTransport) -> None:
        super().connection_made(transport)

    def datagram_received(self, data: bytes, addr: typing.Tuple[typing.Union[str, Any], int]) -> None:
        self.logger.debug(f'received {len(data)} bytes')
        self._packets.put_nowait((data, addr))
        super().datagram_received(data, addr)

    def error_received(self, exc: Exception) -> None:
        raise exc
        super().error_received(exc)

    async def receive(self):
        return await asyncio.wait_for(self._packets.get(), self.timeout)  # TODO improve timeout


class Node(Server):

    def __init__(
            self,
            peer_host: str,  # ipv4 host
            peer_port: int,  # port
            peer_pub_key: str,
            transport: "AdnlTransport"
    ):
        self.host = peer_host
        self.port = peer_port
        super().__init__(peer_host, peer_port, base64.b64decode(peer_pub_key))
        self.channels: typing.List[AdnlChannel] = []
        self.seqno = 1
        self.confirm_seqno = 0
        self.key_id = self.get_key_id()
        self.transport = transport
        self.pinger: asyncio.Task = None
        self.connected = False
        self.logger = logging.getLogger(self.__class__.__name__)

    async def connect(self):
        return await self.transport.connect_to_peer(self)

    async def send_ping(self) -> None:
        random_id = get_random(8)
        resp = await self.transport.send_query_message(tl_schema_name='dht.ping', data={'random_id': random_id}, peer=self)
        assert resp[0].get('random_id') == int.from_bytes(random_id, 'big', signed=True)

    def start_ping(self):
        self.pinger = asyncio.create_task(self.ping())

    async def ping(self):
        while True:
            self.sending = True
            await self.send_ping()
            self.sending = False
            self.logger.debug(f'pinged {self.key_id.hex()}')
            await asyncio.sleep(3)

    async def get_signed_address_list(self):
        return (await self.transport.send_query_message('dht.getSignedAddressList', {}, self))[0]

    @property
    def addr(self) -> typing.Tuple[str, int]:
        """
        :return: ipv4 node address as (host, port)
        """
        return self.host, self.port

    def inc_seqno(self):
        self.seqno += 1

    async def disconnect(self):
        if self.connected:
            self.connected = False
            self.pinger.cancel()


class AdnlTransportError(Exception):
    pass


class AdnlTransport:

    def __init__(self,
                 private_key: bytes = None,
                 tl_schemas_path: str = None,
                 local_address: tuple = ('0.0.0.0', 12000),
                 *args, **kwargs
                 ) -> None:
        """
        ADNL Transport abstract class
        """

        """########### init ###########"""
        self.loop: asyncio.AbstractEventLoop = None
        self.timeout = kwargs.get('timeout', 10)
        self.listener = None
        self.tasks: typing.Dict[str, asyncio.Future] = {}
        self.query_handlers: typing.Dict[str, typing.Callable] = {}

        """########### connection ###########"""
        self.transport: asyncio.DatagramTransport = None
        self.protocol: SocketProtocol = None
        self.local_address = local_address

        """########### TL ###########"""
        if tl_schemas_path is None:
            self.schemas = TlGenerator.with_default_schemas().generate()
        else:
            self.schemas = TlGenerator(tl_schemas_path).generate()
        self.adnl_query_sch = self.schemas.get_by_name('adnl.message.query')
        self.adnl_packet_content_sch = self.schemas.get_by_name('adnl.packetContents')
        self.create_channel_sch = self.schemas.get_by_name('adnl.message.createChannel')

        """########### crypto ###########"""
        self.peers: typing.Dict[bytes, Node] = {}
        if private_key is None:
            private_key = Client.generate_ed25519_private_key()
        self.client = Client(private_key)
        self.local_id = self.client.get_key_id()
        self.channels: typing.Dict[bytes, AdnlChannel] = {}
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

    def _prepare_packet_content_msg(self, data: dict, peer: Node = None) -> dict:
        """
        Adds random bytes, seqno, confirm_seqno and flags in message args if they were not provided
        """
        if 'rand1' not in data or 'rand2' not in data:
            data['rand1'] = self._get_rand()
            data['rand2'] = self._get_rand()

        if data.get('seqno') is None:
            if peer is None:
                raise AdnlTransportError('Must either specify seqno in data or provide peer to method')
            data['seqno'] = peer.seqno
        if data.get('confirm_seqno') is None:
            if peer is None:
                raise AdnlTransportError('Must either specify confirm_seqno in data or provide peer to method')
            data['confirm_seqno'] = peer.confirm_seqno

        return self.compute_flags_for_packet(data)

    def _decrypt_any(self, resp_packet: bytes) -> typing.Tuple[bytes, typing.Optional[Node]]:
        """
        :param resp_packet: bytes of received packet
        :return: decrypted packet and maybe `Node`
        """
        key_id = resp_packet[:32]
        if key_id == self.client.get_key_id():
            server_public_key = resp_packet[32:64]
            checksum = resp_packet[64:96]
            encrypted = resp_packet[96:]

            shared_key = get_shared_key(self.client.x25519_private.encode(),
                                        Server('', 0, server_public_key).x25519_public.encode())
            dec_cipher = create_aes_ctr_sipher_from_key_n_data(shared_key, checksum)
            decrypted = aes_ctr_decrypt(dec_cipher, encrypted)
            assert hashlib.sha256(decrypted).digest() == checksum, 'invalid checksum'
            return decrypted, None
        else:
            for peer_id, channel in self.channels.items():
                if key_id == channel.server_aes_key_id:
                    checksum = resp_packet[32:64]
                    encrypted = resp_packet[64:]
                    decrypted = channel.decrypt(encrypted, checksum)
                    assert hashlib.sha256(decrypted).digest() == checksum, 'invalid checksum'
                    return decrypted, self.peers.get(peer_id)
            raise AdnlTransportError(f'unknown key id from node: {key_id.hex()}')

    def process_outcoming_message(self, message: dict) -> typing.Optional[asyncio.Future]:
        future = self.loop.create_future()
        type_ = message['@type']
        if type_ == 'adnl.message.query':
            self.tasks[message.get('query_id')[::-1].hex()] = future
        elif type_ == 'adnl.message.createChannel':
            self.tasks[message.get('key')] = future
        else:
            raise AdnlTransportError(f'unexpected message sending as a client: {message}')
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

    async def process_incoming_message(self, message: dict):
        if message['@type'] == 'adnl.message.answer':
            future = self.tasks.pop(message.get('query_id'))
            future.set_result(message['answer'])
        elif message['@type'] == 'adnl.message.confirmChannel':
            future = self.tasks.pop(message.get('peer_key'))
            future.set_result(message)
        elif message['@type'] == 'adnl.message.query':
            query = message.get('query')
            handler = self.query_handlers.get(query['@type'])
            if handler:
                handler(query)
        else:
            raise AdnlTransportError(f'unexpected message type received as a client: {message}')

    async def listen(self):
        while True:
            if not self.tasks:
                await asyncio.sleep(0)
                continue
            packet, addr = await self.protocol.receive()
            decrypted, peer = self._decrypt_any(packet)
            if decrypted is None:
                continue
            response = self.schemas.deserialize(decrypted)[0]
            if peer is not None:
                received_confirm_seqno = response.get('confirm_seqno', 0)
                if received_confirm_seqno > peer.confirm_seqno:
                    peer.confirm_seqno = received_confirm_seqno

            message = response.get('message')
            messages = response.get('messages')

            if message:
                await self.process_incoming_message(message)
            if messages:
                for message in messages:
                    await self.process_incoming_message(message)

    async def send_message_in_channel(self, data: dict, channel: typing.Optional[AdnlChannel] = None, peer: Node = None) -> list:

        if peer is None:
            raise AdnlTransportError('Must provide peer')

        data = self._prepare_packet_content_msg(data, peer)
        sending_seqno = data.get('seqno')

        futures = self._create_futures(data)

        if channel is None:
            if not len(peer.channels):
                raise AdnlTransportError(f'Peer has no channels and channel was not provided')
            channel = peer.channels[0]

        if peer.seqno == sending_seqno:
            peer.inc_seqno()
        else:
            raise Exception(f'sending seqno {sending_seqno}, client seqno: {peer.seqno}')
        serialized = self.schemas.serialize(self.adnl_packet_content_sch, data)
        res = channel.encrypt(serialized)

        self.transport.sendto(res, addr=peer.addr)
        result = await asyncio.wait_for(self._receive(futures), self.timeout)

        return result

    async def send_message_outside_channel(self, data: dict, peer: Node) -> list:
        """
        Serializes, signs and encrypts sending message.
        :param peer: peer
        :param data: data for `adnl.packetContents` TL Scheme
        :return: decrypted and deserialized response
        """
        data = self._prepare_packet_content_msg(data, peer)
        sending_seqno = data.get('seqno')

        data = self.compute_flags_for_packet(data)

        futures = self._create_futures(data)

        serialized1 = self.schemas.serialize(self.adnl_packet_content_sch, self.compute_flags_for_packet(data))
        signature = self.client.sign(serialized1)
        serialized2 = self.schemas.serialize(self.adnl_packet_content_sch,
                                             self.compute_flags_for_packet(data | {'signature': signature}))

        checksum = hashlib.sha256(serialized2).digest()
        shared_key = get_shared_key(self.client.x25519_private.encode(), peer.x25519_public.encode())
        init_cipher = create_aes_ctr_sipher_from_key_n_data(shared_key, checksum)
        data = aes_ctr_encrypt(init_cipher, serialized2)

        res = peer.get_key_id() + self.client.ed25519_public.encode() + checksum + data
        self.transport.sendto(res, addr=(peer.host, peer.port))

        if peer.seqno == sending_seqno:
            peer.inc_seqno()
        else:
            raise Exception(f'sending seqno {sending_seqno}, client seqno: {peer.seqno}')

        result = await asyncio.wait_for(self._receive(futures), self.timeout)
        return result

    async def start(self):
        self.loop = asyncio.get_running_loop()
        self.transport, self.protocol = await self.loop.create_datagram_endpoint(
            lambda: SocketProtocol(timeout=self.timeout),
            local_addr=self.local_address
        )
        self.listener = self.loop.create_task(self.listen())
        return

    async def connect_to_peer(self, peer: Node) -> list:
        """
        Connects to the peer, creates channel and asks for a signed list in channel.
        :return: response dict for dht.getSignedAddressList
        """
        # self.transport, self.protocol = await self.loop.create_datagram_endpoint(lambda: SocketProtocol(timeout=self.timeout))

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

        messages = await self.send_message_outside_channel(data, peer)
        confirm_channel = messages[0]
        assert confirm_channel.get('@type') == 'adnl.message.confirmChannel', (f'expected adnl.message.confirmChannel,'
                                                                               f' got {confirm_channel.get("@type")}')
        assert confirm_channel['peer_key'] == channel_client.ed25519_public.encode().hex()

        channel_peer = Server(peer.host, peer.port, bytes.fromhex(confirm_channel['key']))
        channel = AdnlChannel(channel_client, channel_peer, self.local_id, peer.get_key_id())
        self.channels[peer.get_key_id()] = channel
        peer.channels.append(channel)

        # test channel:  todo remove

        data = {
            'message': get_addr_list_message,
        }

        result = await self.send_message_in_channel(data, channel, peer)
        peer.start_ping()
        peer.connected = True

        return result

    async def close(self):
        self.transport.close()

    async def send_query_message(self, tl_schema_name: str, data: dict, peer: Node) -> list[dict]:
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

        result = await self.send_message_in_channel(data, None, peer)
        return result

    async def send_answer_message(self, ):
        pass
    async def send_custom_message(self, message: bytes, peer) -> list:
        # TODO test

        custom_message = {
            '@type': 'adnl.message.custom',
            'data': message
        }

        data = {
            'message': custom_message,
        }

        result = await self.send_message_in_channel(data, peer)
        return result
