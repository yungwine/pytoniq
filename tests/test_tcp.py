import asyncio
import time

from tonpylib.liteclient.client_tcp import AdnlClientTcp


host = '65.21.141.231'
port = 17728

pub_key_b64 = 'BYSVpL7aPk0kU5CtlsIae/8mf2B/NrBi7DKmepcjX6Q='


async def test(req_num: int):
    client = AdnlClientTcp(
        host,
        port,
        pub_key_b64
    )
    await client.connect()
    tasks = [client.get_masterchain_info() for _ in range(req_num)]

    start = time.perf_counter()
    res = await asyncio.gather(*tasks)
    t = time.perf_counter() - start

    assert len(res) == req_num

    # its like .cancel(), will be  implemented directly in client class
    for i in asyncio.all_tasks(client.loop):
        if i.get_name() in ('pinger', 'listener'):
            i.cancel()

    return t


async def main():
    client = AdnlClientTcp(
        host,
        port,
        pub_key_b64
    )
    await client.connect()

    await client.get_masterchain_info()
    last = (await client.get_masterchain_info_ext())['last']
    resp = await client.get_time()
    resp = await client.get_version()
    resp = await client.get_state(last['workchain'], last['shard'], last['seqno'], last['root_hash'], last['file_hash'])
    resp = await client.get_block_header(last['workchain'], last['shard'], last['seqno'], last['root_hash'], last['file_hash'])

    raw_state = await client.raw_get_account_state('EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG')
    state = await client.get_account_state('EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG')

    print(raw_state)  # {'last_trans_lt': 39064423000006, 'balance': {'grams': 445885900290, 'other': {'dict': None}}, 'state': {'type_': 'account_active', 'state_init': {'split_depth': None, 'special': None, 'code': <Cell 80[FF00F4A413F4BCF2C80B] -> 1 refs>, 'data': <Cell 321[000000E729A9A317C1B3226CE226D6D818BAFE82D3633AA0F06A6C677272D1F9B760FF0D0DCF56D800] -> 0 refs>, 'library': None}}}
    print(state)  # <SimpleAccount EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG: state=active, balance={'grams': 445885900290, 'other': {'dict': None}}>

    stack = await client.run_get_method(address='EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG', method='seqno', stack=[])

    print(stack)  # [231]


    await client.close()


if __name__ == '__main__':
    asyncio.run(main(), debug=True)
