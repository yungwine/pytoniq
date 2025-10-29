from unittest.mock import Mock

import pytest
import random

import pytest_asyncio

from pytoniq import BaseWallet, WalletV3R1, WalletV3R2, WalletV4R2, WalletV5R1, WalletV5WalletID, begin_cell, \
    WalletError


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


def test_v5_wallet_id():
    """
    calculated default values serialisation:
    network_global_id = -239, workchain = 0, version = 0', subwallet_number = 0 (client context)
    gives wallet_id = 2147483409
    network_global_id = -239, workchain = -1, version = 0', subwallet_number = 0 (client context)
    gives wallet_id = 8388369
    network_global_id = -3, workchain = 0, version = 0', subwallet_number = 0 (client context)
    gives wallet_id = 2147483645
    network_global_id = -3, workchain = -1, version = 0', subwallet_number = 0 (client context)
    gives wallet_id = 8388605
    """

    assert WalletV5WalletID(workchain=0, version=0, network_global_id=-239).pack() == 2147483409
    assert WalletV5WalletID(workchain=-1, version=0, network_global_id=-239).pack() == 8388369
    assert WalletV5WalletID(workchain=0, version=0, network_global_id=-3).pack() == 2147483645
    assert WalletV5WalletID(workchain=-1, version=0, network_global_id=-3).pack() == 8388605

    wid = WalletV5WalletID.unpack(2147483409, -239)
    assert wid.workchain == 0 and wid.version == 0 and wid.subwallet_number == 0 and wid.network_global_id == -239

    wid = WalletV5WalletID.unpack(8388369, -239)
    assert wid.workchain == -1 and wid.version == 0 and wid.subwallet_number == 0 and wid.network_global_id == -239

    wid = WalletV5WalletID.unpack(2147483645, -3)
    assert wid.workchain == 0 and wid.version == 0 and wid.subwallet_number == 0 and wid.network_global_id == -3
    wid = WalletV5WalletID.unpack(8388605, -3)
    assert wid.workchain == -1 and wid.version == 0 and wid.subwallet_number == 0 and wid.network_global_id == -3

    for workchain in [-1, 0, 1, 2, 3, 4, 5, 127, -128]:
        for version in range(0, 15):
            for subwallet_number in range(0, 1000):
                for network_global_id in [-239, -3, 0, 1, 12345, -12345]:

                    wid1 = WalletV5WalletID(workchain=workchain, version=version,
                                            subwallet_number=subwallet_number,
                                            network_global_id=network_global_id)
                    packed = wid1.pack()
                    wid2 = WalletV5WalletID.unpack(packed, network_global_id)

                    assert wid2.context is None
                    assert wid1.workchain == wid2.workchain
                    assert wid1.version == wid2.version
                    assert wid1.subwallet_number == wid2.subwallet_number
                    assert wid1.network_global_id == wid2.network_global_id

                    # it passes, but too slow to run every time because of slow cells :(
                    # cs = begin_cell().store_uint((packed ^ network_global_id) & 0xFFFFFFFF, 32).end_cell().begin_parse()
                    # cs.skip_bits(1)
                    # assert cs.load_int(8) == workchain
                    # assert cs.load_uint(8) == version
                    # assert cs.load_uint(15) == subwallet_number

    wid = WalletV5WalletID(context=0, network_global_id=-239)
    assert wid.pack() == 4294967057
    wid = WalletV5WalletID.unpack(4294967057, -239)
    assert wid.workchain is None and wid.context == 0

    wid = WalletV5WalletID(context=1000, network_global_id=-3)
    assert wid.pack() == 4294966293
    wid = WalletV5WalletID.unpack(4294966293, -3)
    assert wid.workchain is None and wid.context == 1000

@pytest.mark.asyncio
async def test_wallet_v5_creation(client):
    with pytest.raises(WalletError):  # wallet_id or network_global_id is required
        m, w = await WalletV5R1.create(client, wc=-1)
    m, w = await WalletV5R1.create(client, wc=0, network_global_id=-239)
    assert w.wallet_id == 2147483409
    assert w.unpacked_wallet_id(-239).workchain == 0
    assert w.unpacked_wallet_id(-239).network_global_id == -239
    assert w.unpacked_wallet_id(-239).version == 0
    assert w.unpacked_wallet_id(-239).subwallet_number == 0

    w2 = await WalletV5R1.from_mnemonic(client, mnemonics=m, network_global_id=-239)
    assert w2.address == w.address

    w3 = await WalletV5R1.from_mnemonic(client, mnemonics=m, wallet_id=2147483409)
    assert w3.address == w.address

