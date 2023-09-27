# pytoniq

[![PyPI version](https://badge.fury.io/py/pytoniq.svg)](https://badge.fury.io/py/pytoniq) 
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/pytoniq)](https://pypi.org/project/pytoniq/)
![](https://pepy.tech/badge/pytoniq) 
[![Downloads](https://static.pepy.tech/badge/pytoniq)](https://pepy.tech/project/pytoniq) 
[![](https://img.shields.io/badge/%F0%9F%92%8E-TON-grey)](https://ton.org)

Pytoniq is a Python SDK for the TON Blockchain. This library extends [pytoniq-core](https://github.com/yungwine/pytoniq-core) with native `LiteClient` and `ADNL`.

If you have any questions join Python - TON [developers chat](https://t.me/pythonnton).

## Documentation
[GitBook](https://yungwine.gitbook.io/pytoniq-doc/)

## Installation

```commandline
pip install pytoniq 
```

## Examples
You can find them in the [examples](examples/) folder.

## ADNL

```python
from pytoniq.adnl.adnl import AdnlTransport, Node

adnl = AdnlTransport(timeout=3)

# start adnl receiving server
await adnl.start()

# take peer from public config
peer = Node('172.104.59.125', 14432, "/YDNd+IwRUgL0mq21oC0L3RxrS8gTu0nciSPUrhqR78=", adnl)
await adnl.connect_to_peer(peer)
# or await peer.connect()

await peer.disconnect()

# send pings
await asyncio.sleep(10)

# stop adnl receiving server
await adnl.close()
```

## DHT

```python
import time

from pytoniq.adnl.adnl import AdnlTransport
from pytoniq.adnl.dht import DhtClient, DhtNode


adnl = AdnlTransport(timeout=5)
client = DhtClient.from_mainnet_config(adnl)

await adnl.start()

foundation_adnl_addr = '516618cf6cbe9004f6883e742c9a2e3ca53ed02e3e36f4cef62a98ee1e449174'
resp = await client.find_value(key=DhtClient.get_dht_key_id(bytes.fromhex(foundation_adnl_addr)))
print(resp)
#  {'@type': 'dht.valueFound', 'value': {'key': {'key': {'id': '516618cf6cbe9004f6883e742c9a2e3ca53ed02e3e36f4cef62a98ee1e449174', 'name': b'address', 'idx': 0, '@type': 'dht.key'}, 'id': {'key': '927d3e71e3ce651c3f172134d39163f70e4c792169e39f3d520bfad9388ad4ca', '@type': 'pub.ed25519'}, 'update_rule': {'@type': 'dht.updateRule.signature'}, 'signature': b"g\x08\xf8yo\xed1\xb83\x17\xb9\x10\xb4\x8f\x00\x17]D\xd2\xae\xfa\x87\x9f\xf7\xfa\x192\x971\xee'2\x83\x0fk\x03w\xbb0\xfcU\xc8\x89Zm\x8e\xba\xce \xfc\xde\xf2F\xdb\x0cI*\xe0\xaeN\xef\xc2\x9e\r", '@type': 'dht.keyDescription'}, 'value': {'@type': 'adnl.addressList', 'addrs': [{'@type': 'adnl.address.udp', 'ip': -1537433966, 'port': 3333}], 'version': 1694227845, 'reinit_date': 1694227845, 'priority': 0, 'expire_at': 0}, 'ttl': 1695832194, 'signature': b'z\x8aW\x80k\xceXQ\xff\xb9D{C\x98T\x02e\xef&\xfc\xb6\xde\x80y\xf7\xb4\x92\xae\xd2\xd0\xbakU}3\xfa\xec\x03\xb6v\x98\xb0\xcb\xe8\x05\xb9\xd0\x07o\xb6\xa0)I\x17\xcb\x1a\xc4(Dt\xe6y\x18\x0b', '@type': 'dht.value'}}

key = client.get_dht_key(id_=adnl.client.get_key_id())
ts = int(time.time())
value_data = {
    'addrs': [
        {
            "@type": "adnl.address.udp",
            "ip": 1111111,
            "port": 12000
        }
    ],
    'version': ts,
    'reinit_date': ts,
    'priority': 0,
    'expire_at': 0,
}

value = client.schemas.serialize(client.schemas.get_by_name('adnl.addressList'), value_data)

stored = await client.store_value(  # store our address list in dht as value
    key=key,
    value=value,
    private_key=adnl.client.ed25519_private.encode(),
    ttl=100,
    try_find_after=False
)

print(stored)  # True if value was stored, False otherwise

# disconnect from all peers
await client.close()
```

## LiteClient

### Blockstore
The library can prove all data it receives from a Liteserver (Learn about trust levels [here](https://yungwine.gitbook.io/pytoniq-doc/liteclient/trust-levels)).
If you want to use `LiteClient` with the zero trust level, at the first time run library will prove block link from the `init_block` to the last masterchain block.
Last proved blocks will be stored in the `.blockstore` folder. The file data contains `ttl` and `gen_utime` of the last synced key block, its data serialized according to the `BlockIdExt` TL scheme (but in big–endian), last synced masterchain block data. 
Filename is first 88 bytes of data described above with init block hash.

### General LiteClient usage examples

#### Client initializing

```python
from pytoniq import LiteClient


async def main():
    client = LiteClient.from_mainnet_config(  # choose mainnet, testnet or custom config dict
        ls_i=0,  # index of liteserver from config
        trust_level=2,  # trust level to liteserver
        timeout=15  # timeout not includes key blocks synchronization as it works in pytonlib
    )

    await client.connect()
    
    await client.reconnect()  # can reconnect to an exising object if had any errors

    await client.close()

```

#### Blocks transactions scanning

See `BlockScanner` code [here](examples/blocks/block_scanner.py).

```python
from pytoniq_core import BlockIdExt
from pytoniq import LiteClient
from examples.blocks.block_scanner import BlockScanner  # this import is not available if downloaded from pypi

async def handle_block(block: BlockIdExt):
    if block.workchain == -1:  # skip masterchain blocks
        return
    print(block)
    transactions = await client.raw_get_block_transactions_ext(block)
    for transaction in transactions:
        print(transaction.in_msg)


client = LiteClient.from_mainnet_config(ls_i=14, trust_level=0, timeout=20)


async def main():

    await client.connect()
    await BlockScanner(client=client, block_handler=handle_block).run()
```
