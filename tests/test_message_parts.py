"""Offline tests for reassembling messages split into adnl.message.part (no network needed)."""
import base64
import hashlib

import pytest
from pytoniq_core.crypto.ciphers import Client

from pytoniq.adnl.adnl import AdnlTransport, Node


PAYLOAD = bytes(range(256)) * 12  # ~3 KB, needs several parts


def split(message: bytes, size: int = 1024) -> list:
    hash_ = hashlib.sha256(message).hexdigest()
    return [{'@type': 'adnl.message.part', 'hash': hash_, 'total_size': len(message), 'offset': offset,
             'data': message[offset:offset + size]}
            for offset in range(0, len(message), size)]


@pytest.fixture
def setup():
    transport = AdnlTransport(timeout=1)
    peer = Node('10.0.0.1', 1, base64.b64encode(Client(Client.generate_ed25519_private_key()).ed25519_public.encode()).decode(), transport)
    received = []

    async def process_custom_message(message, peer_):
        received.append(message)

    transport._process_custom_message = process_custom_message
    return transport, peer, received


def custom_message(transport: AdnlTransport, data: bytes = PAYLOAD) -> bytes:
    return transport.schemas.serialize('adnl.message.custom', {'data': data})


@pytest.mark.asyncio
async def test_assembled_message_is_processed_and_forgotten(setup):
    transport, peer, received = setup

    for part in split(custom_message(transport)):
        await transport._process_incoming_message(part, peer)

    assert len(received) == 1
    assert received[0]['data'] == PAYLOAD
    assert transport._message_parts == {}


@pytest.mark.asyncio
async def test_parts_out_of_order(setup):
    transport, peer, received = setup

    for part in reversed(split(custom_message(transport))):
        await transport._process_incoming_message(part, peer)

    assert [m['data'] for m in received] == [PAYLOAD]
    assert transport._message_parts == {}


@pytest.mark.asyncio
async def test_duplicate_part_is_ignored(setup):
    transport, peer, received = setup
    parts = split(custom_message(transport))

    for part in [parts[0]] + parts:
        await transport._process_incoming_message(part, peer)

    assert [m['data'] for m in received] == [PAYLOAD]
    assert transport._message_parts == {}


@pytest.mark.asyncio
async def test_stale_incomplete_message_is_dropped(setup):
    transport, peer, received = setup
    lost = split(custom_message(transport, b'a' * 3000))
    fresh = split(custom_message(transport, b'b' * 3000))

    await transport._process_incoming_message(lost[0], peer)
    transport._message_parts[lost[0]['hash']]['created_at'] -= AdnlTransport.MESSAGE_PARTS_TTL + 1
    await transport._process_incoming_message(fresh[0], peer)

    assert list(transport._message_parts) == [fresh[0]['hash']]
    assert received == []


@pytest.mark.asyncio
async def test_fresh_incomplete_messages_are_kept(setup):
    transport, peer, received = setup
    first = split(custom_message(transport, b'a' * 3000))
    second = split(custom_message(transport, b'b' * 3000))

    await transport._process_incoming_message(first[0], peer)
    await transport._process_incoming_message(second[0], peer)
    for part in first[1:]:
        await transport._process_incoming_message(part, peer)

    assert [m['data'] for m in received] == [b'a' * 3000]
    assert list(transport._message_parts) == [second[0]['hash']]
