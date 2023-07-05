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
    start = time.time()
    client = AdnlClientTcp(
        host,
        port,
        pub_key_b64
    )
    await client.connect()
    print(time.time() - start)
    start = time.perf_counter()
    print(await client.get_masterchain_info())
    print(await client.run_get_method(address='EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG', method='seqno', stack=[]))
    # print(await client.lookup_block(wc=-1, shard=-9223372036854775808, utime=1679773451))
    # print(await client.get_block(-1, -9223372036854775808, 30293401))
    # print(await client.get_masterchain_info())
    print(time.perf_counter() - start)
    i = asyncio.Task
    # client.loop.stop()
    print(asyncio.current_task(client.loop).get_name())
    await client.close()
    # [i.cancel() for i in list(asyncio.all_tasks(client.loop))[1:]]
    # await asyncio.sleep(10)


if __name__ == '__main__':
    asyncio.run(main(), debug=True)
    # asyncio.get_event_loop().run_until_complete(main())

    # client.connect()
