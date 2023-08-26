# pytoniq

[![PyPI version](https://badge.fury.io/py/pytoniq.svg)](https://badge.fury.io/py/pytoniq) 
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/pytoniq)](https://pypi.org/project/tonsdk/)
![](https://pepy.tech/badge/pytoniq) 
[![Downloads](https://static.pepy.tech/badge/pytoniq/month)](https://pepy.tech/project/pytoniq) 
[![](https://img.shields.io/badge/%F0%9F%92%8E-TON-grey)](https://ton.org)

Pytoniq is a Python SDK for the TON Blockchain. This library extends [pytoniq-core](https://github.com/yungwine/pytoniq-core) with native `LiteClient` and `ADNL` over `udp`, `DHT`, `RLDP` (in future).

If you have any questions join Python - TON [developers chat](https://t.me/pythonnton).

## Documentation
[GitBook](https://yungwine.gitbook.io/pytoniq-doc/)

## Installation

```commandline
pip install pytoniq 
```

## Examples
You can find them in the [examples](examples/) folder.

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
