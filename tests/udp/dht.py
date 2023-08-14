import asyncio
import logging
import time

from pytoniq.adnl.udp_client import AdnlUdpClient
from pytoniq.adnl.dht import DhtClient


# host = '65.21.7.173'
# port = 15813
# pub_k = 'fZnkoIAxrTd4xeBgVpZFRm5SvVvSx7eN3Vbe8c83YMk='

host = "172.104.59.125"
port = 14432
pub_k = "/YDNd+IwRUgL0mq21oC0L3RxrS8gTu0nciSPUrhqR78="


async def main():
    udp_client = AdnlUdpClient(
        host=host,
        port=port,
        server_pub_key=pub_k,
        timeout=2
    )

    client = DhtClient([udp_client])

    # print(DhtClient.get_dht_key_id(bytes.fromhex('516618cf6cbe9004f6883e742c9a2e3ca53ed02e3e36f4cef62a98ee1e449174')).hex())
    # print(client.get_dht_key_id_tl(bytes.fromhex('516618cf6cbe9004f6883e742c9a2e3ca53ed02e3e36f4cef62a98ee1e449174')).hex())

    # await client.connect()
    s = time.time()
    print(await client.find_value(key=DhtClient.get_dht_key_id(bytes.fromhex('516618cf6cbe9004f6883e742c9a2e3ca53ed02e3e36f4cef62a98ee1e449174'))))
    print(time.time() - s)
    # print(await asyncio.gather(*[client.get_signed_address_list() for _ in range(50)]))
    # print(await client.get_signed_address_list())

    # resp = await udp_client.send_query_message('dht.findValue', data={'key': 'b30af0538916421b46df4ce580bf3a29316831e0c3323a7f156df0236c5b2f75', 'k': 6})
    #
    # print(resp)

    # print(await client.send_custom_message(b'hello'))
# logging.basicConfig(level=5)

if __name__ == '__main__':
    asyncio.run(main())
