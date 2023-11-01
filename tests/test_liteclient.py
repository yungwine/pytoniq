import logging

import pytest

import random
from pytoniq import LiteClient


@pytest.mark.asyncio
async def test_init():
    client = LiteClient.from_mainnet_config(random.randint(0, 13), trust_level=2)
    await client.connect()
    await client.close()

    client = LiteClient.from_testnet_config(random.randint(0, 5), trust_level=2)
    await client.connect()
    await client.close()

    client = LiteClient.from_mainnet_config(random.randint(0, 13), trust_level=1)
    await client.connect()
    await client.close()

    client = LiteClient.from_testnet_config(random.randint(0, 5), trust_level=1)
    await client.connect()
    await client.close()

    client = LiteClient.from_mainnet_config(random.randint(0, 13), trust_level=0)
    await client.connect()
    await client.close()

    client = LiteClient.from_testnet_config(random.randint(0, 5), trust_level=0)
    await client.connect()
    await client.close()


@pytest.mark.asyncio
async def test_methods():
    client = LiteClient.from_mainnet_config(random.randint(0, 13), trust_level=2)
    await client.connect()
    await client.get_masterchain_info()
    await client.get_config_all()
    await client.raw_get_block(client.last_mc_block)
    await client.close()


@pytest.mark.asyncio
async def test_get_method():
    client = LiteClient.from_mainnet_config(random.randint(0, 13), trust_level=2)
    await client.connect()

    result = await client.run_get_method(address='EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG', method='seqno',
                                         stack=[])
    assert isinstance(result[0], int)
