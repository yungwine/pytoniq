# pytoniq

Pytoniq is a Python SDK for the TON Blockchain. 
Currently, it has native ADNL over TCP connection to Liteservers,
boc types implementation, wrappers for almost all TLB schemes from block.tlb,
automaic TL schemes serialization/deserialization,
some popular contracts wrappers.

* Work in progress

## Documentation
[GitBook](https://yungwine.gitbook.io/pytoniq-doc/)

## Installation

```commandline
pip install pytoniq 
```

## Examples
You can find them in the [examples](examples/) folder.

## Blockstore
The library can prove all data it receives from a Liteserver (Learn about trust levels [here](https://yungwine.gitbook.io/pytoniq-doc/liteclient/trust-levels)).
If you want to use `LiteClient` with the zero trust level, at the first time run library will prove block link from the `init_block` to the last masterchain block.
Last proved blocks will be stored in the `.blockstore` folder. The file data contains `ttl` and `gen_utime` of the last synced key block, its data serialized according to the `BlockIdExt` TL scheme (but in big–endian), last synced masterchain block data. 
Filename is first 88 bytes of data described above with init block hash.

## General usage examples

### Transactions parsing
```python
import asyncio

from pytoniq import LiteClient, MessageAny


async def main():
    client = LiteClient.from_mainnet_config(ls_i=0, trust_level=2)

    await client.connect()

    trs = await client.get_transactions(address='EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG', count=3)
    print(trs)  # [{'account_addr': '6f5bc67986e06430961d9df00433926a4cd92e597ddd8aa6043645ac20bd1782', 'lt': 39515024000004, 'prev_trans_hash': b'\xe93\xfaM"\xc6Cz\x1a\x8a\xfad\x8fe:\xf9sP!\xa4\x8bG\x02KJm^)w\x02Vq', 'prev_trans_lt': 39515024000003, 'now': 1690098531, 'outmsg_cnt': 0, 'orig_status': {'type_': 'active'}, 'end_status': {'type_': 'active'}, 'in_msg': {'info': {'ihr_disabled': True, 'bounce': True, 'bounced': False, 'src': Address<EQAPYSNXK9Ha7o8Z2cnROAYC22-IMzczCNIX7LsU39YZH8bP>, 'dest': Address<EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG>, 'value': {'grams': 1000, 'other': None}, 'value_coins': 1000, 'ihr_fee': 0, 'fwd_fee': 733339, 'created_lt': 39515024000003, 'created_at': 1690098531}, 'init': None, 'body': <Cell 0[] -> 0 refs>}, 'out_msgs': None, 'total_fees': {'grams': 0, 'other': None}, 'state_update': {'old_hash': b'\xd6U\xcc\x0bD\xf2\xaeh\xcf\xe8\xb7I\xa8v\x1a9\xee\x87\x12\xa0\xdb#\xe4\xc3\xa5\xf3\xf5\xae&\x01\xc7\xa7', 'new_hash': b"\x05\xa9\x7fx\xac\r'\xe2\x0e\xddX\xd2M\xe7\xd4\x19ZG\x08J\xe0\r\xeaW\xdd\xf5\xbdX\x86\x82\xf6*"}, 'description': {'type_': 'ordinary', 'credit_first': False, 'storage_ph': {'storage_fees_collected': 0, 'storage_fees_due': None, 'status_change': {'type_': 'unchanged'}}, 'credit_ph': {'due_fees_collected': None, 'credit': {'grams': 1000, 'other': None}}, 'compute_ph': {'type_': 'skipped', 'reason': {'type_': 'no_gas'}}, 'action': None, 'aborted': True, 'bounce': {'type_': 'nofunds', 'msg_size': {'cells': None, 'bits': None}, 'req_fwd_fees': 1000000}, 'destroyed': False}}, {'account_addr': '6f5bc67986e06430961d9df00433926a4cd92e597ddd8aa6043645ac20bd1782', 'lt': 39515024000003, 'prev_trans_hash': b'>y\xa3L\xd9\x15\x92\xc0P\x93\x8a\x86D`H\xa0\x87Z}S\xb7\xc1h\x97\x1cL\xe3\xf7\xb1\x1f\xa4\x8e', 'prev_trans_lt': 39514911000001, 'now': 1690098531, 'outmsg_cnt': 0, 'orig_status': {'type_': 'active'}, 'end_status': {'type_': 'active'}, 'in_msg': {'info': {'ihr_disabled': True, 'bounce': True, 'bounced': False, 'src': Address<EQAPYSNXK9Ha7o8Z2cnROAYC22-IMzczCNIX7LsU39YZH8bP>, 'dest': Address<EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG>, 'value': {'grams': 1000, 'other': None}, 'value_coins': 1000, 'ihr_fee': 0, 'fwd_fee': 733339, 'created_lt': 39515024000002, 'created_at': 1690098531}, 'init': None, 'body': <Cell 0[] -> 0 refs>}, 'out_msgs': None, 'total_fees': {'grams': 91, 'other': None}, 'state_update': {'old_hash': b'\x03}\xbb\x93v\x00\xa7\xc7w\x96\x07\x14\x9a\xafo\xb0\xc3\x16n)\xc4\x02i\x99s\xef\x1f\xf0\xb2\xb6\xd77', 'new_hash': b'\xd6U\xcc\x0bD\xf2\xaeh\xcf\xe8\xb7I\xa8v\x1a9\xee\x87\x12\xa0\xdb#\xe4\xc3\xa5\xf3\xf5\xae&\x01\xc7\xa7'}, 'description': {'type_': 'ordinary', 'credit_first': False, 'storage_ph': {'storage_fees_collected': 91, 'storage_fees_due': None, 'status_change': {'type_': 'unchanged'}}, 'credit_ph': {'due_fees_collected': None, 'credit': {'grams': 1000, 'other': None}}, 'compute_ph': {'type_': 'skipped', 'reason': {'type_': 'no_gas'}}, 'action': None, 'aborted': True, 'bounce': {'type_': 'nofunds', 'msg_size': {'cells': None, 'bits': None}, 'req_fwd_fees': 1000000}, 'destroyed': False}}, {'account_addr': '6f5bc67986e06430961d9df00433926a4cd92e597ddd8aa6043645ac20bd1782', 'lt': 39514911000001, 'prev_trans_hash': b'\xdc#q\x05\x98\x7f\x90\xa8\xde\x85\xf5\xab\x0bqB\xb9\xae\xb1\xe9:\x8b;t\xf4\\\xa1\xda\xc1V\xa1B\xa7', 'prev_trans_lt': 39496961000001, 'now': 1690098174, 'outmsg_cnt': 1, 'orig_status': {'type_': 'active'}, 'end_status': {'type_': 'active'}, 'in_msg': {'info': {'src': None, 'dest': Address<EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG>, 'import_fee': 0}, 'init': None, 'body': <Cell 648[0317AED6DDEFC03BD811F8EAD1DB34F4FA74E5187B864CADF0C5849E36352CDF995D732967AD0EB474DB41166E1E51FB6D337BA6A0F9C261B4498FA1E37CAE0E29A9A31764BCDA33000000F10000000003] -> 1 refs>}, 'out_msgs': [{'info': {'ihr_disabled': True, 'bounce': False, 'bounced': False, 'src': Address<EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG>, 'dest': Address<EQAPYSNXK9Ha7o8Z2cnROAYC22-IMzczCNIX7LsU39YZH8bP>, 'value': {'grams': 45840000, 'other': None}, 'value_coins': 45840000, 'ihr_fee': 0, 'fwd_fee': 2773355, 'created_lt': 39514911000002, 'created_at': 1690098174}, 'init': {'split_depth': None, 'special': None, 'code': <Cell 80[FF00F4A413F4BCF2C80B] -> 1 refs>, 'data': <Cell 353[29A9A31700000000000000005E014E37FFE03A0AB54E904F3C2F87001114C084B0D0F3E3BEC934BDDEB655D400] -> 0 refs>, 'library': None}, 'body': <Cell 0[] -> 0 refs>}], 'total_fees': {'grams': 10134337, 'other': None}, 'state_update': {'old_hash': b'\xfe\xb4\x8a\x18!\xb4\x82\x8cg\x8aXfkI|\xcb\xa9i\xcaEh\x9c%q\x14M\xd3\xe5\xbf\xb2\xe0E', 'new_hash': b'\x03}\xbb\x93v\x00\xa7\xc7w\x96\x07\x14\x9a\xafo\xb0\xc3\x16n)\xc4\x02i\x99s\xef\x1f\xf0\xb2\xb6\xd77'}, 'description': {'type_': 'ordinary', 'credit_first': True, 'storage_ph': {'storage_fees_collected': 14692, 'storage_fees_due': None, 'status_change': {'type_': 'unchanged'}}, 'credit_ph': None, 'compute_ph': {'type_': 'vm', 'success': True, 'msg_state_used': False, 'account_activated': False, 'gas_fees': 3308000, 'gas_used': 3308, 'gas_limit': None, 'gas_credit': 10000, 'mode': 0, 'exit_code': 0, 'exit_arg': None, 'vm_steps': 68, 'vm_init_state_hash': b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', 'vm_final_state_hash': b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'}, 'action': {'success': True, 'valid': True, 'no_funds': False, 'status_change': {'type_': 'unchanged'}, 'total_fwd_fees': 4160000, 'total_action_fees': 1386645, 'result_code': 0, 'result_arg': None, 'tot_actions': 1, 'spec_actions': 0, 'skipped_actions': 0, 'msgs_created': 1, 'action_list_hash': b'd\xeb\xc4\x9ax*\xe5\x8ds\x03\xd6p\xd1\xb5Z\xd6s{\x8da\x81\x8e\x9b$\x91\x96[yLg\xe6&', 'tot_msg_size': {'cells': 13, 'bits': 2666}}, 'aborted': False, 'bounce': None, 'destroyed': False}}]

    transaction = trs[2]
    print(transaction.in_msg.info)  # {'ihr_disabled': True, 'bounce': True, 'bounced': False, 'src': Address<EQAPYSNXK9Ha7o8Z2cnROAYC22-IMzczCNIX7LsU39YZH8bP>, 'dest': Address<EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG>, 'value': {'grams': 1000, 'other': None}, 'value_coins': 1000, 'ihr_fee': 0, 'fwd_fee': 733339, 'created_lt': 39515024000003, 'created_at': 1690098531}
    body = transaction.in_msg.body
    print([body.begin_parse()])  # [<Slice 648[0317AED6DDEFC03BD811F8EAD1DB34F4FA74E5187B864CADF0C5849E36352CDF995D732967AD0EB474DB41166E1E51FB6D337BA6A0F9C261B4498FA1E37CAE0E29A9A31764BCDA33000000F10000000003] -> 1 refs>]

    await client.close()


if __name__ == '__main__':
    asyncio.run(main())

```

### Blocks parsing

```python

import asyncio

from pytoniq.liteclient import LiteClient
from pytoniq.tlb import Block, ValueFlow, ShardAccounts
from pytoniq.tl import BlockIdExt


async def parse_block(client: LiteClient, block: BlockIdExt):
    full_block = await client.raw_get_block(block)
    value_flow: ValueFlow = full_block.value_flow
    print(value_flow.fees_collected.grams)  # 1007000010
    accounts: ShardAccounts = full_block.state_update.old.shard_state_unsplit.accounts
    print(accounts)  # ({40756874397635192262439020188088563828720515972064165042579090230945048213995: {'account': {'addr': Address<EQBaG5LL_CsF2hOq0D-nk71YcihyR71_1o33FnlG5cS56590>, 'storage_stat': {'used': {'cells': 22, 'bits': 5697, 'public_cells': None}, 'last_paid': 1690187357, 'due_payment': None}, 'storage': {'last_trans_lt': 39542571000003, 'balance': {'grams': 62352028502, 'other': None}, 'state': {'type_': 'account_active', 'state_init': {'split_depth': None, 'special': None, 'code': <Cell 288[0101FEB5FF6820E2FF0D9483E7E0D62C817D846789FB4AE580C878866D959DABD5C00007] -> 0 refs>, 'data': <Cell 321[000023E429A9A317B28A8042597CD3F1591A8B3A0EE7DAEF53E8FA7D5378A618AA80BE1EB48FC8E700] -> 0 refs>, 'library': None}}}}, 'last_trans_hash': b'\xfe}o\x83\xaf\x7f\xcf\x9e .\xc6\x0b\x96\x9el\xae8\xa6\xa9N[O\x89\xb8\xd3\xbaf\x89\xdf.\xdb\xd4', 'last_trans_lt': 39542571000001, 'cell': <Cell 320[FE7D6F83AF7FCF9E202EC60B969E6CAE38A6A94E5B4F89B8D3BA6689DF2EDBD4000023F6B8E5E0C1] -> 1 refs>}}, [{'split_depth': 0, 'balance': {'grams': 5553445990447918, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 5553446978130918, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 5553447242093167, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 5553449597627584, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 5553449680120571, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 5553502425603666, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 5553551498198270, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 5554171371732038, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 5554810996626740, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 5556695368115041, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 5570820341996106, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 5582868370124598, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 5668324449113770, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 5983054304100620, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 6643915352221766, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 99915737789528586, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 198985701626791490, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 379795173339356597, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 62352028502, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 62353858158, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 62451366404, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 64501434435, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 115078782628, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 132264475468, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 413217320912, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 431027638506, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 465652010665, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 855472014247, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 12697170876788, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 23277573167204, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 65993263389943, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 1628994778449415, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 2334912485572297, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 4383884219022332, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 5493159230272353, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 31059031289819148, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 126234268026871666, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 506029441366228263, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 719987176953810690, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 1802443900690706273, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 2725693542936016491, 'other': None}}])


async def main():
    client = LiteClient.from_mainnet_config(ls_i=0, trust_level=2)

    await client.connect()

    old_blk = client.last_shard_blocks[0]  # last basechain block
    await parse_block(client, old_blk)
    while True:
        while client.last_shard_blocks[0] == old_blk:
            await asyncio.sleep(0)
            continue
        old_blk = client.last_shard_blocks[0]
        await parse_block(client, old_blk)


if __name__ == '__main__':
    asyncio.run(main())

```
