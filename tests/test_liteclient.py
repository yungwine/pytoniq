import asyncio
import time

import pytest
import random

import pytest_asyncio

from pytoniq import LiteClient


@pytest_asyncio.fixture
async def client():
    while True:
        client = LiteClient.from_mainnet_config(random.randint(0, 15), trust_level=1)
        try:
            await client.connect()
            yield client
            await client.close()
            return
        except:
            continue


@pytest.mark.asyncio
async def test_init():
    client = LiteClient.from_mainnet_config(ls_i=0, trust_level=2)
    await client.connect()
    await client.reconnect()
    await client.close()

    client = LiteClient.from_testnet_config(ls_i=12, trust_level=2)
    await client.connect()
    await client.reconnect()
    await client.close()

    # try:
    #     client = LiteClient.from_mainnet_config(random.randint(0, 8), trust_level=0)
    #     await client.connect()
    #     await client.close()
    # except asyncio.TimeoutError:
    #     print('skipping')


@pytest.mark.asyncio
async def test_methods(client: LiteClient):
    await client.get_masterchain_info()
    await client.get_config_all()
    await client.raw_get_block(client.last_mc_block)
    lib = 'c245262b8c2bce5e9fcd23ca334e1d55fa96d4ce69aa2817ded717cefcba3f73'
    fake_lib = '0000000000000000000000000000000000000000000000000000000000000000'
    res = await client.get_libraries([lib, lib, fake_lib, lib])
    assert len(res) == 2
    assert res[lib].hash.hex() == lib
    assert res[fake_lib] is None


@pytest.mark.asyncio
async def test_get_method(client: LiteClient):

    result = await client.run_get_method(address='EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG', method='seqno',
                                         stack=[])
    assert isinstance(result[0], int)
    result2 = await client.run_get_method_local(address='EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG', method='seqno',
                                                stack=[])
    assert result2 == result
