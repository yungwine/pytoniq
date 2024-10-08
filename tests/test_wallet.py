from unittest.mock import Mock

import pytest
import random

import pytest_asyncio

from pytoniq import BaseWallet, WalletV3R1, WalletV3R2, WalletV4R2


@pytest_asyncio.fixture
async def client():
    c = Mock()

    async def raw_get_account_state(*args, **kwargs):
        return None, None

    c.raw_get_account_state = raw_get_account_state
    return c


@pytest.mark.asyncio
async def test_wallets(client):
    m0, w0 = await BaseWallet.create(client, version='v3r1')
    m1, w1 = await WalletV3R2.create(client)
    m2, w2 = await WalletV4R2.create(client)
    w3 = await WalletV3R2.from_mnemonic(client, mnemonics=m1)
    w4 = await WalletV4R2.from_mnemonic(client, mnemonics=m2)
    w5 = await BaseWallet.from_mnemonic(client, mnemonics=m0, version='v3r1')
    w6 = await WalletV3R1.from_mnemonic(client, mnemonics=m0)

    assert w0.address == w5.address == w6.address
    assert w1.address == w3.address
    assert w2.address == w4.address
