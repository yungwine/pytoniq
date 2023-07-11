import asyncio
import time

from tonpylib.liteclient.client_tcp import AdnlClientTcp
from tonpylib.tl.block import BlockIdExt

host = '65.21.141.231'
port = 17728

pub_key_b64 = 'BYSVpL7aPk0kU5CtlsIae/8mf2B/NrBi7DKmepcjX6Q='


async def main():
    client = AdnlClientTcp(
        host,
        port,
        pub_key_b64
    )
    await client.connect()

    await client.get_masterchain_info()
    last = (await client.get_masterchain_info_ext())['last']
    # s = time.time()
    # print(await client.wait_masterchain_seqno(last['seqno'] + 2, 10))
    # print(time.time() - s)
    # state = await client.raw_get_all_shards_info(BlockIdExt.from_dict(last))

    blk, blk_data = await client.lookup_block(-1, 0, 31041506)
    # trs = await client.raw_get_transactions('EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG', 10)
    tr = await client.get_one_transaction('Ef8zMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzM0vF', lt=39202528000001, block=blk)

    print(tr)
    input()
    tr = await client.get_one_transaction('Ef8zMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzMzM0vF', lt=39202528000001, block=blk)
    print(tr)
    state = await client.raw_get_shard_info(BlockIdExt.from_dict(last), wc=0, shard=last['shard'], exact=True)
    input()
    state = await client.raw_get_all_shards_info(BlockIdExt.from_dict(last))
    resp = await client.get_time()
    resp = await client.get_version()
    resp = await client.get_state(last['workchain'], last['shard'], last['seqno'], last['root_hash'], last['file_hash'])
    resp = await client.get_block(last['workchain'], last['shard'], last['seqno'], last['root_hash'], last['file_hash'])
    resp = await client.lookup_block(last['workchain'], last['shard'], last['seqno'])

    resp = await client.get_block_header(last['workchain'], last['shard'], last['seqno'], last['root_hash'], last['file_hash'])

    raw_state = await client.raw_get_account_state('EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG')
    state = await client.get_account_state('EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG')

    print(raw_state)  # {'last_trans_lt': 39064423000006, 'balance': {'grams': 445885900290, 'other': {'dict': None}}, 'state': {'type_': 'account_active', 'state_init': {'split_depth': None, 'special': None, 'code': <Cell 80[FF00F4A413F4BCF2C80B] -> 1 refs>, 'data': <Cell 321[000000E729A9A317C1B3226CE226D6D818BAFE82D3633AA0F06A6C677272D1F9B760FF0D0DCF56D800] -> 0 refs>, 'library': None}}}
    print(state)  # <SimpleAccount EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG: state=active, balance=445885900290>

    stack = await client.run_get_method(address='EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG', method='seqno', stack=[])

    print(stack)  # [231]

    await client.close()


if __name__ == '__main__':
    asyncio.run(main(), debug=True)
