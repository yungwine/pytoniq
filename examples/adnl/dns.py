import asyncio
import hashlib
import logging

from pytoniq_core import Address, Builder, Slice
from pytoniq import LiteClient, AdnlTransport, DhtClient, Node, DhtNode


client = LiteClient.from_mainnet_config(5, 2)


async def main():
    await client.connect()
    logging.basicConfig(level=logging.DEBUG)

    # resolve domain foundation.ton
    request_stack = [Builder().store_uint(0, 8).end_cell().begin_parse(), int.from_bytes(hashlib.sha256(b'site').digest(), 'big')]
    stack = await client.run_get_method(address='EQB43-VCmf17O7YMd51fAvOjcMkCw46N_3JMCoegH_ZDo40e', method='dnsresolve', stack=request_stack)
    await client.close()
    cs: Slice = stack[1].begin_parse()
    assert cs.load_bytes(2) == b'\xad\x01'
    adnl_addr = cs.load_bytes(32)

    print(adnl_addr.hex())  # foundation.ton node adnl address

    adnl = AdnlTransport(timeout=3)
    await adnl.start()

    dht_client = DhtClient.from_mainnet_config(adnl)

    value = await dht_client.find_value(
        key=DhtClient.get_dht_key_id(adnl_addr),
        timeout=15
    )

    print(value)  # dht.valueFound

    await dht_client.close()
    await adnl.close()

asyncio.run(main())
