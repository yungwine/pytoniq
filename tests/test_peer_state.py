"""Offline tests for peer bookkeeping in ADNL, DHT and overlay transports (no network needed)."""
import asyncio
import base64

import pytest
from pytoniq_core.crypto.ciphers import Client
from pytoniq_core.tl import TlGenerator

from pytoniq.adnl import dht as dht_module
from pytoniq.adnl.adnl import AdnlTransport, AdnlTransportError, Node
from pytoniq.adnl.dht import DhtClient, DhtNode, DhtValueNotFoundError
from pytoniq.adnl.overlay.overlay import OverlayNode, OverlayTransport
from pytoniq.adnl.overlay.overlay_manager import process_get_capabilities_request, process_get_random_peers_request


def new_key() -> Client:
    return Client(Client.generate_ed25519_private_key())


def b64_pub(client: Client) -> str:
    return base64.b64encode(client.ed25519_public.encode()).decode()


@pytest.mark.asyncio
async def test_confirm_channel_goes_to_registered_peer():
    transport = AdnlTransport(timeout=1)
    peer_key, our_channel, their_channel = new_key(), new_key(), new_key()
    registered = Node('10.0.0.1', 1, b64_pub(peer_key), transport)
    throwaway = Node('10.0.0.1', 1, b64_pub(peer_key), transport)  # what process_packet() builds for a `from` packet
    transport.peers[registered.key_id] = registered
    transport.pending_channels[registered.key_id] = our_channel
    peer_key_hex = our_channel.ed25519_public.encode().hex()
    transport.tasks[peer_key_hex] = asyncio.get_running_loop().create_future()

    transport._process_confirm_channel(
        {'peer_key': peer_key_hex, 'key': their_channel.ed25519_public.encode().hex()}, throwaway)

    assert len(registered.channels) == 1
    assert throwaway.channels == []


@pytest.mark.asyncio
async def test_cancelled_connect_unregisters_peer():
    transport = AdnlTransport(timeout=1)
    peer = Node('10.0.0.1', 1, b64_pub(new_key()), transport)

    async def no_answer(*_):
        await asyncio.sleep(10)

    transport.send_message_outside_channel = no_answer

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(transport.connect_to_peer(peer), 0.01)
    assert peer.key_id not in transport.peers
    assert transport.pending_channels == {}

    # a retry must be possible instead of failing with "already connected"
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(transport.connect_to_peer(peer), 0.01)


@pytest.mark.asyncio
async def test_failed_connect_still_unregisters_peer():
    transport = AdnlTransport(timeout=1)
    peer = Node('10.0.0.1', 1, b64_pub(new_key()), transport)

    async def broken(*_):
        raise AdnlTransportError('boom')

    transport.send_message_outside_channel = broken

    with pytest.raises(AdnlTransportError):
        await transport.connect_to_peer(peer)
    assert peer.key_id not in transport.peers


def test_dht_node_copies_are_equal():
    transport = AdnlTransport(timeout=1)
    key = b64_pub(new_key())
    known, copy = DhtNode('10.0.0.1', 1, key, transport), DhtNode('10.0.0.1', 1, key, transport)
    other = DhtNode('10.0.0.2', 1, b64_pub(new_key()), transport)

    assert known == copy
    assert known != other
    assert len({known, copy, other}) == 2
    # DhtClient.find_value() merges with nodes_set.union(new): the known (possibly connected) object must stay
    assert next(iter({known}.union({copy}))) is known


@pytest.mark.asyncio
async def test_get_overlay_node_not_found_is_none(monkeypatch):
    transport = AdnlTransport(timeout=1)
    client = DhtClient([DhtNode('10.0.0.1', 1, b64_pub(new_key()), transport)], transport)

    async def not_found(*_, **__):
        raise DhtValueNotFoundError('nobody stores it')

    monkeypatch.setattr(client, 'find_value', not_found)
    monkeypatch.setattr(dht_module, 'verify_sign', lambda *_: True)
    node = {'id': {'key': new_key().ed25519_public.encode().hex()}, 'overlay': '00' * 32, 'version': 1,
            'signature': b'\x00' * 64}

    assert await client.get_overlay_node(node, transport) is None


@pytest.mark.asyncio
async def test_get_random_peers_asks_the_given_peer():
    overlay = OverlayTransport(overlay_id='00' * 32, timeout=1)
    target = OverlayNode('10.0.0.1', 1, b64_pub(new_key()), overlay)
    for i in range(3):
        neighbour = OverlayNode(f'10.0.0.{i + 2}', 1, b64_pub(new_key()), overlay)
        overlay.peers[neighbour.key_id] = neighbour
    asked = []

    async def send_query_message(tl_schema_name, data, peer):
        asked.append(peer)
        return [{'@type': 'overlay.nodes', 'nodes': []}]

    overlay.send_query_message = send_query_message

    await overlay.get_random_peers(target)

    assert asked == [target]


@pytest.mark.asyncio
async def test_peers_that_connect_to_overlay_are_overlay_nodes():
    server = OverlayTransport(overlay_id='00' * 32, local_address=('127.0.0.1', None), timeout=2)
    client = OverlayTransport(overlay_id='00' * 32, local_address=('127.0.0.1', None), timeout=2)
    server.set_query_handler('overlay.getRandomPeers', lambda q: process_get_random_peers_request(q, server))
    await server.start()
    await client.start()
    try:
        await client.connect_to_peer(OverlayNode('127.0.0.1', server.local_address[1], b64_pub(server.client), client))

        inbound = server.peers[client.local_id]
        assert isinstance(inbound, OverlayNode)
        # not signed, so it is left out of getRandomPeers queries and answers
        assert process_get_random_peers_request(None, server)['nodes'] == [server.get_signed_myself()]
    finally:
        for transport in (server, client):
            for peer in list(transport.peers.values()):
                await peer.disconnect()
        await asyncio.sleep(0.1)  # close() can hang if it cancels the listener in the middle of a packet
        for transport in (server, client):
            await transport.close()


def test_capabilities_answer_matches_schema():
    schemas = TlGenerator.with_default_schemas().generate()

    raw = schemas.serialize('tonNode.capabilities', process_get_capabilities_request(None))

    assert schemas.deserialize(raw)[0] == process_get_capabilities_request(None)
