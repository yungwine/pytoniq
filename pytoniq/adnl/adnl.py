import asyncio
import base64
import inspect
import logging
import random
import time
import hashlib
import typing
from asyncio import transports
from typing import Any

from pytoniq_core.tl.generator import TlGenerator

from pytoniq_core.crypto.ciphers import Server, Client, AdnlChannel, get_random, aes_ctr_encrypt, aes_ctr_decrypt, \
    get_shared_key, create_aes_ctr_sipher_from_key_n_data


class SocketProtocol(asyncio.DatagramProtocol):

    def __init__(self, timeout: int = 10):
        # https://github.com/eerimoq/asyncudp/blob/main/asyncudp/__init__.py
        self._error = None
        self._packets = asyncio.Queue(500000)
        self.timeout = timeout
        self.logger = logging.getLogger(self.__class__.__name__)

    def connection_made(self, transport: transports.DatagramTransport) -> None:
        super().connection_made(transport)

    def datagram_received(self, data: bytes, addr: typing.Tuple[typing.Union[str, Any], int]) -> None:
        self.logger.debug(f'received {len(data)} bytes from {addr}; queue {self._packets.qsize()}')
        try:
            self._packets.put_nowait((data, addr))
        except asyncio.QueueFull:
            self.logger.warning('Queue is full, dropping packet')
        super().datagram_received(data, addr)

    def error_received(self, exc: Exception) -> None:
        self.logger.warning(f'error received: {exc}')
        super().error_received(exc)

    async def receive(self):
        return await self._packets.get()


class Node(Server):

    PING_INTERVAL = 60

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
        self._last_ping_at = time.time()
        self._lost_pings = 0

    @property
    def lost_pings(self):
        return self._lost_pings

    def reset_pings(self):
        self._last_ping_at = time.time()
        self._lost_pings = 0

    async def connect(self):
        return await self.transport.connect_to_peer(self)

    async def send_ping(self) -> None:
        random_id = get_random(8)
        resp = await self.transport.send_query_message(tl_schema_name='dht.ping', data={'random_id': random_id},
                                                       peer=self)
        assert resp[0].get('random_id') == int.from_bytes(random_id, 'big', signed=True)

    def start_ping(self):
        self.pinger = asyncio.create_task(self.ping())

    async def ping(self):
        while True:
            try:
                await self.send_ping()
                self.reset_pings()
                self.logger.debug(f'pinged {self.key_id.hex()}')
            except asyncio.TimeoutError:
                self._lost_pings += 1
                if self._lost_pings > 3 and self._last_ping_at < time.time() - 15:
                    if self.key_id in self.transport.peers:
                        self.transport.peers.pop(self.key_id)
                    await self.disconnect()
            await asyncio.sleep(self.PING_INTERVAL)

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
            self.logger.debug(f'disconnected {self.key_id.hex()}')
            self.connected = False
            self.pinger.cancel()
            self.transport.peers.pop(self.key_id, None)
        for ch in self.channels:
            self.transport.channels.pop(ch.server_aes_key_id, None)
        self.channels = []
        self.seqno = 1
        self.confirm_seqno = 0
        self.reset_pings()


class AdnlTransportError(Exception):
    pass


class AdnlTransport:

    def __init__(self,
                 private_key: bytes = None,
                 tl_schemas_path: str = None,
                 local_address: tuple = ('0.0.0.0', None),
                 *args, **kwargs
                 ) -> None:
        """
        ADNL Transport abstract class
        """

        """########### init ###########"""
        self.loop: asyncio.AbstractEventLoop = None
        self.timeout = kwargs.get('timeout', 10)
        self.listener: asyncio.Task = None
        self.logger = logging.getLogger(self.__class__.__name__)
        self.tasks: typing.Dict[str, asyncio.Future] = {}
        self.query_handlers: typing.Dict[str, typing.Callable] = {}
        self.custom_handlers: typing.Dict[str, typing.Callable] = {}
        self._message_parts: typing.Dict[str, dict] = {}  # {'hash': {'remained': int, 'parts': list}}
        self.inited = False
        self.pending_channels = {}

        """########### connection ###########"""
        self.transport: asyncio.DatagramTransport = None
        self.protocol: SocketProtocol = None
        if local_address[1] is None:
            local_address = local_address[0], random.randint(10000, 60000)
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
        if resp_packet.startswith(self.local_id):
            server_public_key = resp_packet[32:64]
            checksum = resp_packet[64:96]
            encrypted = resp_packet[96:]

            peer_crypto = Server('', 0, server_public_key)

            shared_key = get_shared_key(self.client.x25519_private.encode(),
                                        peer_crypto.x25519_public.encode())

            dec_cipher = create_aes_ctr_sipher_from_key_n_data(shared_key, checksum)
            decrypted = aes_ctr_decrypt(dec_cipher, encrypted)
            assert hashlib.sha256(decrypted).digest() == checksum, 'invalid checksum'
            return decrypted, None
        else:
            key_id = resp_packet[:32]
            channel = self.channels.get(key_id)
            if channel:
                peer_id = channel.peer_id
                checksum = resp_packet[32:64]
                encrypted = resp_packet[64:]
                decrypted = channel.decrypt(encrypted, checksum)
                assert hashlib.sha256(decrypted).digest() == checksum, 'invalid checksum'
                return decrypted, self.peers.get(peer_id)
            self.logger.debug(f'unknown key id from node: {key_id.hex()}')
            return b'', None

    def _process_outcoming_message(self, message: dict) -> typing.Optional[asyncio.Future]:
        future = self.loop.create_future()
        type_ = message['@type']
        if type_ == 'adnl.message.query':
            id_ = message.get('query_id')[::-1].hex()
            self.tasks[id_] = future
        elif type_ == 'adnl.message.createChannel':
            id_ = message.get('key')
            self.tasks[id_] = future
        else:
            return
        future.id = id_
        return future

    def _create_futures(self, data: dict) -> typing.List[asyncio.Future]:
        futures = []
        if data.get('message'):
            future = self._process_outcoming_message(data['message'])
            if future is not None:
                futures.append(future)

        if data.get('messages'):
            for message in data['messages']:
                future = self._process_outcoming_message(message)
                if future is not None:
                    futures.append(future)
        return futures

    @staticmethod
    async def _receive(futures: typing.List[asyncio.Future]) -> list:
        return list(await asyncio.gather(*futures))

    async def _process_incoming_message(self, message: dict, peer: Node):
        if peer:
            self.logger.debug(f'Received message {message} from peer {peer.key_id.hex()}')
        if message['@type'] == 'adnl.message.answer':
            future = self.tasks.pop(message.get('query_id'), None)
            if future and not future.done():
                future.set_result(message['answer'])
        elif message['@type'] == 'adnl.message.confirmChannel':
            self._process_confirm_channel(message, peer)
        elif message['@type'] == 'adnl.message.createChannel':
            await self._process_create_channel(message, peer)
        elif message['@type'] == 'adnl.message.query':
            if peer is None:
                self.logger.debug(f'Received query message from unknown peer: {message}')
                return
            peer.reset_pings()
            await self._process_query_message(message, peer)
        elif message['@type'] == 'adnl.message.custom':
            if peer is None:
                # should not ever happen fixme
                self.logger.debug(f'Received custom message from unknown peer: {message}')
                return
            peer.reset_pings()
            await self._process_custom_message(message, peer)
        elif message['@type'] == 'adnl.message.part':
            hash_ = message['hash']
            if hash_ not in self._message_parts:
                self._message_parts[hash_] = {'remained': message['total_size'], 'parts': []}

            self._message_parts[hash_]['remained'] -= len(message['data'])
            self._message_parts[hash_]['parts'].append(message)

            if self._message_parts[hash_]['remained'] == 0:
                try:
                    data = self._collect_adnl_message_parts(hash_)
                except:
                    return
                if isinstance(data, dict) and data['@type'] != 'adnl.message.part':  # to avoid infinity recursion, but should never happen
                    await self._process_incoming_message(data, peer)
        else:
            self.logger.debug(f'unexpected message type received: {message}')
            # raise AdnlTransportError(f'unexpected message type received: {message}')

    def _store_new_channel(self, channel_client: Client, key: str, peer: Node):
        channel_peer = Server(peer.host, peer.port, bytes.fromhex(key))
        channel = AdnlChannel(channel_client, channel_peer, self.local_id, peer.key_id)
        channel.peer_id = peer.key_id
        self.channels[channel.server_aes_key_id] = channel
        peer.channels.append(channel)

    def _process_confirm_channel(self, message: dict, peer: Node):
        if message.get('peer_key') in self.tasks:
            future = self.tasks.pop(message.get('peer_key'))
            if not future.done():
                future.set_result(message)
            if peer.key_id not in self.pending_channels:
                return

            channel_client = self.pending_channels.get(peer.key_id)  # add channel to the object from connect_to_peer
            self._store_new_channel(channel_client, message['key'], peer)

    async def _process_create_channel(self, message: dict, peer: Node):
        if peer.key_id in self.peers:
            return  # drop packet since peer is already connected
        key = message.get('key')
        if key is None:
            return
        channel_client = Client(Client.generate_ed25519_private_key())

        ts = int(time.time())

        confirm_channel_message = {
            '@type': 'adnl.message.confirmChannel',
            'peer_key': key,
            'key': channel_client.ed25519_public.encode().hex(),
            'date': ts
        }

        data = {
            'from_short': {'id': self.local_id.hex()},
            'message': confirm_channel_message,
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

        self._store_new_channel(channel_client, key, peer)

        peer.connected = True
        self.peers[peer.key_id] = peer

        await self.send_message_outside_channel(data, peer)
        peer.start_ping()

    def _collect_adnl_message_parts(self, hash_: str, deserialize_after: bool = True):
        if hash_ not in self._message_parts:
            raise AdnlTransportError(f'Provided hash not in message parts')
        parts = sorted(self._message_parts[hash_]['parts'], key=lambda i: i['offset'])
        full_data = b''
        for part in parts:
            full_data += part['data']
        if deserialize_after:
            return self.schemas.deserialize(full_data)[0]

    async def _process_query_message(self, message: dict, peer: Node):
        query = message.get('query')
        # it's divided into separate method because some higher level protocols over ADNL need specific query processing
        await self._process_query_handler(message, query, peer)

    async def _process_query_handler(self, message: dict, query: dict, peer: Node):
        # try to get handler for specific query and if there is no, try to get default handler
        handler = self.query_handlers.get(query['@type'], self.query_handlers.get(None))
        if handler:
            if inspect.iscoroutinefunction(handler):
                response = await handler(query)
            else:
                response = handler(query)
            if response is not None:
                await self.send_answer_message(response, message.get('query_id'), peer)

    async def _process_custom_message(self, message: dict, peer: Node):
        data = message.get('data')
        await self._process_custom_message_handler(data, peer)

    async def _process_custom_message_handler(self, data: dict, peer: Node):
        handler = self.custom_handlers.get(data['@type'], self.custom_handlers.get(None))
        if handler:
            if inspect.iscoroutinefunction(handler):
                response = await handler(data)
            else:
                response = handler(data)
            if response is not None:
                await self.send_custom_message(response, peer)

    def set_query_handler(self, type_: str, handler: typing.Callable) -> None:
        """
        :param type_: TL type of message
        :param handler: function to handle message. **Must** return dict or bytes or None. If
            None returned than answer won't be sent to the sender
        :return:
        """
        self.query_handlers[type_] = handler

    def set_default_query_handler(self, handler: typing.Callable):
        """
        Same as `set_query_handler` when there is no handlers for query specific type.
        :param handler:
        :return:
        """
        self.set_query_handler(None, handler)

    def set_custom_message_handler(self, type_: str, handler: typing.Callable):
        """
        :param type_: TL type of message
        :param handler: function to handle message. **Must** return dict or bytes or None. If
            None returned than answer won't be sent to the sender.
        :return:
        """
        self.custom_handlers[type_] = handler

    def set_default_custom_message_handler(self, handler: typing.Callable):
        """
        Same as `set_custom_message_handler` when there is no handlers for query specific type.
        :param handler:
        :return:
        """
        self.set_custom_message_handler(None, handler)

    async def process_packet(self, packet_data: bytes, addr: tuple):

        try:
            decrypted, peer = self._decrypt_any(packet_data)
            if not decrypted:
                return
            packet, _ = self.schemas.deserialize(decrypted)
            if not isinstance(packet, dict):  # must be deserialized
                return
        except:
            return

        if peer is None:
            if 'from' in packet:
                peer = Node(addr[0], addr[1], base64.b64encode(bytes.fromhex(packet['from']['key'])).decode(), self)
            if 'from_short' in packet:
                peer = self.peers.get(bytes.fromhex(packet['from_short']['id']))

        if peer is not None:
            received_seqno = packet.get('seqno', 0)
            if received_seqno > peer.confirm_seqno:
                peer.confirm_seqno = received_seqno

        message = packet.get('message')
        messages = packet.get('messages', [])

        if message:
            messages = [message] + messages
        for message in messages:
            try:
                await self._process_incoming_message(message, peer)
            finally:
                continue

    async def listen(self):
        while True:
            packet_data, addr = await self.protocol.receive()
            try:
                await asyncio.wait_for(self.process_packet(packet_data, addr), timeout=1)
            except asyncio.TimeoutError:
                self.logger.warning(f'packet processing timeout: len({packet_data}) from {addr}')
                continue
            except Exception as e:
                self.logger.warning(f'packet processing error: {e}')
                continue

    async def _wait(self, futures: typing.List[asyncio.Future]):
        try:
            result = await asyncio.wait_for(self._receive(futures), self.timeout)
            return result
        except asyncio.TimeoutError:
            raise
        finally:
            for f in futures:
                self.tasks.pop(f.id, None)

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
        result = await self._wait(futures)

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
        if futures:
            return await self._wait(futures)


    async def start(self):
        self.loop = asyncio.get_running_loop()
        self.transport, self.protocol = await self.loop.create_datagram_endpoint(
            lambda: SocketProtocol(timeout=self.timeout),
            local_addr=self.local_address,
            reuse_port=True
        )
        self.listener = self.loop.create_task(self.listen())
        self.inited = True
        return

    def _get_default_message(self):
        random_id = get_random(8)
        return {
            '@type': 'adnl.message.query',
            'query_id': get_random(32),
            'query': {'@type': 'dht.ping', 'random_id': random_id},
        }

    async def connect_to_peer(self, peer: Node) -> list:
        """
        Connects to the peer, creates channel and asks for a signed list in channel.
        :param peer: peer connect to
        :return: response dict for default message
        """

        if peer.key_id in self.peers:
            raise AdnlTransportError(f"Peer {peer.key_id.hex()} is already connected")

        ts = int(time.time())
        channel_client = Client(Client.generate_ed25519_private_key())
        create_channel_message = {
            '@type': 'adnl.message.createChannel',
            'key': channel_client.ed25519_public.encode().hex(),
            'date': ts
        }

        default_message = self._get_default_message()

        from_ = self.schemas.serialize(self.schemas.get_by_name('pub.ed25519'), data={'key': self.client.ed25519_public.encode().hex()})
        data = {
            'from': from_,
            # 'from_short': {'id': self.client.get_key_id().hex()},
            # 'message': create_channel_message,
            'messages': [create_channel_message, default_message],
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

        self.pending_channels[peer.key_id] = channel_client
        self.peers[peer.key_id] = peer

        try:
            messages = await self.send_message_outside_channel(data, peer)
        except Exception as e:
            self.peers.pop(peer.key_id)
            await peer.disconnect()
            raise e
        finally:
            self.pending_channels.pop(peer.key_id, None)
        confirm_channel = messages[0]
        assert confirm_channel.get('@type') == 'adnl.message.confirmChannel', (f'expected adnl.message.confirmChannel,'
                                                                               f' got {confirm_channel.get("@type")}')
        assert confirm_channel['peer_key'] == channel_client.ed25519_public.encode().hex()

        peer.start_ping()
        peer.connected = True

        return messages[1]

    async def close(self):
        self.listener.cancel()
        while not self.listener.cancelled():
            await asyncio.sleep(0)
        self.transport.abort()
        self.inited = False

    async def send_query_message(self, tl_schema_name: str, data: dict, peer: Node) -> typing.List[dict]:
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

    async def send_answer_message(self, response: typing.Union[dict, bytes], query_id: bytes, peer: Node):
        message = {
            '@type': 'adnl.message.answer',
            'query_id': query_id,
            'answer': response
        }

        data = {
            'message': message,
        }
        return await self.send_message_in_channel(data, None, peer)

    async def send_custom_message(self, message: typing.Union[dict, bytes], peer: Node) -> list:

        custom_message = {
            '@type': 'adnl.message.custom',
            'data': message
        }

        data = {
            'message': custom_message,
        }

        result = await self.send_message_in_channel(data, None, peer)
        return result
