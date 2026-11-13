import time

import pytest

from pytoniq.liteclient import sync as sync_module
from pytoniq_core.tl.block import BlockIdExt


def block(seqno: int, fill: int) -> BlockIdExt:
    return BlockIdExt(workchain=-1, shard=-9223372036854775808, seqno=seqno,
                      root_hash=bytes([fill]) * 32, file_hash=bytes([fill + 1]) * 32)


class ClientWithoutForwardLinks:
    """Proves to_block without any forward link, so it never sets last_key_block itself."""

    def __init__(self):
        self.last_key_block = None
        self.calls = []

    async def get_mc_block_proof(self, known_block, target_block, return_best_key_block=False):
        self.calls.append(known_block)
        return None, 0


@pytest.mark.asyncio
async def test_sync_sets_last_key_block_from_stored_block(monkeypatch):
    # https://github.com/yungwine/pytoniq/issues/33: with trust_level=0, connect() sometimes failed with
    # AttributeError on None because sync() left client.last_key_block unset.
    init_block = block(1, 1)
    stored_key = block(40_000_000, 3)
    stored_mc = block(40_000_123, 5)
    to_block = stored_mc
    key_ts = int(time.time()) - 3600
    stored = sync_module.blocks_to_bytes(sync_module.persistent_state_ttl(key_ts), key_ts, stored_key, stored_mc)
    monkeypatch.setattr(sync_module, "get_last_stored_blocks", lambda init_hash: stored)
    monkeypatch.setattr(sync_module, "store_blocks", lambda *args, **kwargs: None)
    client = ClientWithoutForwardLinks()

    assert await sync_module.sync(client, to_block=to_block, init_block=init_block)

    assert client.calls == [stored_mc]
    assert client.last_key_block == stored_key
