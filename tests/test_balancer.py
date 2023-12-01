import pytest

from pytoniq import LiteBalancer

from pytoniq_core.tlb.config import ConfigParam0
from pytoniq_core import Address, Cell


@pytest.mark.asyncio
async def test_init():
    client = LiteBalancer.from_mainnet_config(trust_level=1)
    await client.start_up()
    await client.close_all()

    client = LiteBalancer.from_testnet_config(trust_level=1)
    await client.start_up()
    await client.close_all()


@pytest.mark.asyncio
async def test_account_state():
    client = LiteBalancer.from_mainnet_config(trust_level=1)
    await client.start_up()
    params = await client.get_config_params(params=[0])
    param: ConfigParam0 = params[0]
    state, _ = await client.raw_get_account_state(Address((-1, param.config_addr)))
    data: Cell = state.storage.state.state_init.data
    cs = data.begin_parse()
    cs.skip_bits(32)  # seqno
    assert cs.load_bytes(32) == b'\x00' * 32
    await client.close_all()
