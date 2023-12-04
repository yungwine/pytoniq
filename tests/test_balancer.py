import pytest
import pytest_asyncio

from pytoniq import LiteBalancer

from pytoniq_core.tlb.config import ConfigParam0, ConfigParam1
from pytoniq_core import Address, Cell


@pytest.mark.asyncio
async def test_init():
    client = LiteBalancer.from_mainnet_config(trust_level=1)
    await client.start_up()
    await client.close_all()

    client = LiteBalancer.from_testnet_config(trust_level=1)
    await client.start_up()
    await client.close_all()


@pytest_asyncio.fixture
async def client():
    client = LiteBalancer.from_mainnet_config(trust_level=1)
    await client.start_up()
    return client


@pytest.mark.asyncio
async def test_account_state(client: LiteBalancer):
    params = await client.get_config_params(params=[0])
    param: ConfigParam0 = params[0]
    state, _ = await client.raw_get_account_state(Address((-1, param.config_addr)))
    data: Cell = state.storage.state.state_init.data
    cs = data.begin_parse()
    cs.skip_bits(32)  # seqno
    assert cs.load_bytes(32) == b'\x00' * 32
    await client.close_all()


@pytest.mark.asyncio
async def test_archival(client: LiteBalancer):
    blk, _ = await client.lookup_block(-1, -2 ** 63, 10, only_archive=True)
    assert blk.root_hash.hex() == 'c1b8e9cb4c3d886d91764d243693119f4972d284ce7be01e739b67fdcbb84ca1'


@pytest.mark.asyncio
async def test_transactions(client: LiteBalancer):
    params = await client.get_config_params(params=[1])
    param: ConfigParam1 = params[1]
    trs = await client.get_transactions(Address((-1, param.elector_addr)), count=200)
    assert len(trs) == 200
    await client.close_all()
