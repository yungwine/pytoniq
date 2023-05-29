import asyncio
import time

from tonpylib.adnl.client_tcp import AdnlClientTcp


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
    start = time.time()
    tasks = [client.get_masterchain_info() for _ in range(1000)]
    await asyncio.gather(*tasks)
    print(time.time() - start)
    # await client.get_masterchain_info()
    await asyncio.sleep(10)

if __name__ == '__main__':
    asyncio.run(main(), debug=True)
    # asyncio.get_event_loop().run_until_complete(main())

    # client.connect()
