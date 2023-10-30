import asyncio
import logging

from pytoniq.adnl.adnl import AdnlTransport, Node


adnl = AdnlTransport(timeout=3)


async def main():
    logging.basicConfig(level=logging.DEBUG)

    # start adnl receiving server
    await adnl.start()

    # can set default handler for any query
    adnl.set_default_query_handler(handler=lambda i: print(i))

    # or provide function to process specific queries
    def process_get_capabilities_request(_):
        return {
            '@type': 'tonNode.capabilities',
            'version': 2,
            'capabilities': 1,
        }

    adnl.set_query_handler(type_='overlay.getCapabilities',
                           handler=lambda i: process_get_capabilities_request(i))

    # take peer from public config
    peer = Node('172.104.59.125', 14432, "/YDNd+IwRUgL0mq21oC0L3RxrS8gTu0nciSPUrhqR78=", adnl)
    await adnl.connect_to_peer(peer)

    # ask peer for something
    await peer.get_signed_address_list()

    # send pings to peer
    await asyncio.sleep(2)

    # can disconnect from peer == stop pings
    # await peer.disconnect()

    # add another peer
    peer = Node('5.161.60.160', 12485, "jXiLaOQz1HPayilWgBWhV9xJhUIqfU95t+KFKQPIpXg=", adnl)

    # second way to connect to peer
    await peer.connect()

    # 2 adnl channels
    print(adnl.channels)

    # check for pings
    await asyncio.sleep(10)

    # stop adnl receiving server
    await adnl.close()


if __name__ == '__main__':
    asyncio.run(main())
