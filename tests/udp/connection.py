import asyncio
import logging

from pytoniq.adnl.udp_client import AdnlUdpClient


# host = '65.21.7.173'
# port = 15813
# pub_k = 'fZnkoIAxrTd4xeBgVpZFRm5SvVvSx7eN3Vbe8c83YMk='

host = "172.104.59.125"
port = 14432
pub_k = "/YDNd+IwRUgL0mq21oC0L3RxrS8gTu0nciSPUrhqR78="


async def main():
    client = AdnlUdpClient(
        host=host,
        port=port,
        server_pub_key=pub_k,
    )

    await client.connect()
    # print(await asyncio.gather(*[client.get_signed_address_list() for _ in range(50)]))
    print(await client.get_signed_address_list())

    resp = await client.send_query_message('dht.findValue', data={'key': 'b30af0538916421b46df4ce580bf3a29316831e0c3323a7f156df0236c5b2f75', 'k': 6})

    print(resp)

    # print(await client.send_custom_message(b'hello'))
# logging.basicConfig(level=5)

if __name__ == '__main__':
    asyncio.run(main())
