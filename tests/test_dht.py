import asyncio
import hashlib
import logging
import time
from pytoniq_core.crypto.ciphers import Server

from pytoniq.adnl.adnl import AdnlTransport
from pytoniq.adnl.dht import DhtClient, DhtNode


adnl = AdnlTransport(timeout=5)


client = DhtClient.from_mainnet_config(adnl)


async def test_dht():
    logging.basicConfig(level=logging.DEBUG)
    await adnl.start()

    foundation_adnl_addr = '516618cf6cbe9004f6883e742c9a2e3ca53ed02e3e36f4cef62a98ee1e449174'
    resp = await client.find_value(key=DhtClient.get_dht_key_id(bytes.fromhex(foundation_adnl_addr)))
    print(resp)

    assert resp['@type'] == 'dht.valueFound'
