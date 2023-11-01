import asyncio
import pytest

from pytoniq.adnl.adnl import AdnlTransport, Node


adnl = AdnlTransport(timeout=3)


@pytest.mark.asyncio
async def test_connection():

    # start adnl receiving server
    await adnl.start()

    # take peer from public config
    peer = Node('172.104.59.125', 14432, "/YDNd+IwRUgL0mq21oC0L3RxrS8gTu0nciSPUrhqR78=", adnl)
    await adnl.connect_to_peer(peer)

    # ask peer for something
    await peer.get_signed_address_list()

    # send pings to peer
    await asyncio.sleep(2)

    await peer.disconnect()

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
