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
    # last = BlockIdExt.from_dict((await client.get_masterchain_info_ext())['last'])

    params = await client.get_config_all()
    print(params)

    params = await client.get_config_params([1, 2, 3, 4])
    print(params)

    await client.close()


if __name__ == '__main__':
    asyncio.run(main(), debug=True)
