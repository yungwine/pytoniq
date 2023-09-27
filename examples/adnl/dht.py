import asyncio
import hashlib
import logging
import time
from pytoniq_core.crypto.ciphers import Server

from pytoniq.adnl.adnl import AdnlTransport
from pytoniq.adnl.dht import DhtClient, DhtNode


adnl = AdnlTransport(timeout=5)

host = "172.104.59.125"
port = 14432
pub_k = "/YDNd+IwRUgL0mq21oC0L3RxrS8gTu0nciSPUrhqR78="
peer = DhtNode('172.104.59.125', 14432, "/YDNd+IwRUgL0mq21oC0L3RxrS8gTu0nciSPUrhqR78=", adnl)

client = DhtClient.from_mainnet_config(adnl)

# or specify known dht peers explicitly:
# client = DhtClient([peer], adnl)


async def main():
    await dht()
    await overlay()

    # disconnect from all peers
    await client.close()


async def dht():
    logging.basicConfig(level=logging.DEBUG)
    await adnl.start()

    foundation_adnl_addr = '516618cf6cbe9004f6883e742c9a2e3ca53ed02e3e36f4cef62a98ee1e449174'
    resp = await client.find_value(key=DhtClient.get_dht_key_id(bytes.fromhex(foundation_adnl_addr)))
    print(resp)
    #  {'@type': 'dht.valueFound', 'value': {'key': {'key': {'id': '516618cf6cbe9004f6883e742c9a2e3ca53ed02e3e36f4cef62a98ee1e449174', 'name': b'address', 'idx': 0, '@type': 'dht.key'}, 'id': {'key': '927d3e71e3ce651c3f172134d39163f70e4c792169e39f3d520bfad9388ad4ca', '@type': 'pub.ed25519'}, 'update_rule': {'@type': 'dht.updateRule.signature'}, 'signature': b"g\x08\xf8yo\xed1\xb83\x17\xb9\x10\xb4\x8f\x00\x17]D\xd2\xae\xfa\x87\x9f\xf7\xfa\x192\x971\xee'2\x83\x0fk\x03w\xbb0\xfcU\xc8\x89Zm\x8e\xba\xce \xfc\xde\xf2F\xdb\x0cI*\xe0\xaeN\xef\xc2\x9e\r", '@type': 'dht.keyDescription'}, 'value': {'@type': 'adnl.addressList', 'addrs': [{'@type': 'adnl.address.udp', 'ip': -1537433966, 'port': 3333}], 'version': 1694227845, 'reinit_date': 1694227845, 'priority': 0, 'expire_at': 0}, 'ttl': 1695832194, 'signature': b'z\x8aW\x80k\xceXQ\xff\xb9D{C\x98T\x02e\xef&\xfc\xb6\xde\x80y\xf7\xb4\x92\xae\xd2\xd0\xbakU}3\xfa\xec\x03\xb6v\x98\xb0\xcb\xe8\x05\xb9\xd0\x07o\xb6\xa0)I\x17\xcb\x1a\xc4(Dt\xe6y\x18\x0b', '@type': 'dht.value'}}

    key = client.get_dht_key(id_=adnl.client.get_key_id())
    ts = int(time.time())
    value_data = {
                'addrs': [
                    {
                        "@type": "adnl.address.udp",
                        "ip": 1111111,
                        "port": 12000
                    }
                ],
                'version': ts,
                'reinit_date': ts,
                'priority': 0,
                'expire_at': 0,
            }

    value = client.schemas.serialize(client.schemas.get_by_name('adnl.addressList'), value_data)

    stored = await client.store_value(  # store our address list in dht as value
        key=key,
        value=value,
        private_key=adnl.client.ed25519_private.encode(),
        ttl=100,
        try_find_after=False
    )

    print(stored)  # True if value was stored, false otherwise


async def overlay():
    """VERY RAW OVERLAY USAGE"""

    # look for basechain overlay nodes

    def get_overlay_key():
        schemes = client.schemas
        sch = schemes.get_by_name('tonNode.shardPublicOverlayId')
        data = {
            "workchain": 0,
            "shard": -9223372036854775808,
            "zero_state_file_hash": "5e994fcf4d425c0a6ce6a792594b7173205f740a39cd56f537defd28b48a0f6e"
        }
        key_id = hashlib.sha256(schemes.serialize(sch, data)).digest()
        sch = schemes.get_by_name('pub.overlay')
        data = {
            'name': key_id
        }
        key_id = schemes.serialize(sch, data)
        return client.get_dht_key_id_tl(id_=hashlib.sha256(key_id).digest(), name=b'nodes')

    resp = await client.find_value(key=get_overlay_key(), timeout=30)
    print(resp)
    # {'@type': 'dht.valueFound', 'value': {'key': {'key': {'id': '12b8a83f098e15ea47fe76d0b0df0986ff6dda1980796b084b0d2a68b2558649', 'name': b'nodes', 'idx': 0, '@type': 'dht.key'}, 'id': {'name': b'\x945\xc2\x12\xdc\x0e\xc5\x1d\xachd\x10\xe9\xba\x98\xf4\xb6\xfc}_\x08\xae\xb9\x16A\t\x17\x8e\xb9P\xdd\xec', '@type': 'pub.overlay'}, 'update_rule': {'@type': 'dht.updateRule.overlayNodes'}, 'signature': b'', '@type': 'dht.keyDescription'}, 'value': {'@type': 'overlay.nodes', 'nodes': [{'id': {'key': 'b557ef2a24d14aca18e129071b2e75562842f0bae1459669afb736f5990a3c61', '@type': 'pub.ed25519'}, 'overlay': '12b8a83f098e15ea47fe76d0b0df0986ff6dda1980796b084b0d2a68b2558649', 'version': 1695829307, 'signature': b'Z\x0e\xc9\xc0MA\xd7\xf5Z\xab\xc3\xa3\xd7\xd0\x96\x97\x8b\x05x5\xbd\xd7\xc4\xe7\xfa5\xd5\x06\xdb\xe2"\x0f>s8\x12\x93\xba\xae\xe5\x9eCI\xab\x98\xe9\x1dx4\x0c\xb4\x8d\xf3\x8e\x01\xdd\x15N\xa6/\x18\xfa\xaf\r'}, {'id': {'key': '6aa8baa5d300a70a83d901028842c8f1ff7244d6ff12c33faf08265949f7ca1d', '@type': 'pub.ed25519'}, 'overlay': '12b8a83f098e15ea47fe76d0b0df0986ff6dda1980796b084b0d2a68b2558649', 'version': 1695315522, 'signature': b'h\xe6\x1c\xfa\xa2\xf8\xf2\x80\xe5}\x15\xf0\x96\xc94N\xe4\xe2\xb6\xfe\xaf\tN8\x11D+\xfb\x95\x92\xe0Tn\xff\xd1\x81(e\xf0\\\x95@[{\xb1\xd4\xd1\xae\xe4&\xa2\xaa\x04\xb2,z%\xd3\nx\xd3h\xc4\t'}, {'id': {'key': 'bb626e1a95b117e8d45cfb9158f2b5e80dae75353f9959320e2af01ea147bc3c', '@type': 'pub.ed25519'}, 'overlay': '12b8a83f098e15ea47fe76d0b0df0986ff6dda1980796b084b0d2a68b2558649', 'version': 1678009360, 'signature': b'\n\x9a\x1b\n\xeb\x9e\x1a\xda\xb1z\xf3\xe7\xf1\x8c\xb6hH\xc5\x7fmc\x02Zv\xac"3\x01\x84Wf\x92@\x11\xa8\xb9\x92\x1f\x86N\xf5\xbc\x15\xca\xe7\xf0\x96i\xf7\xcc~&3\xc8\xb3tZ+\xac\xb9\xd9\x03\xd7\n'}, {'id': {'key': '6f8a107b1ab5ddf6ea286af2d5e29db703c921826ab3e19b1a039987e3baca8b', '@type': 'pub.ed25519'}, 'overlay': '12b8a83f098e15ea47fe76d0b0df0986ff6dda1980796b084b0d2a68b2558649', 'version': 1695829212, 'signature': b"\n\xffS\xf3r\xac@\xd2\xd4.m1\xe4j\xc15\xfai\xc7G\x0bB|L\x1c\xd2.\x98A\xb5\xcd\xe4mw\xc6\x14\xac\x18<\x16J_\xb6\xe8\x96k\xe2`\xe7S\xf2\x1c\xe7\xc2\xd2\x15'\x87\x7fjAo\x04\x05"}, {'id': {'key': '504da3252f966807a7855bdc75498c6dd6f16da384cea76076003dea7fd50a12', '@type': 'pub.ed25519'}, 'overlay': '12b8a83f098e15ea47fe76d0b0df0986ff6dda1980796b084b0d2a68b2558649', 'version': 1661512096, 'signature': b"\xbb\x17\x9c\x9d\x19QO\xcc\xd1\t\n\x11\x1d.\xf1\xad\xdf\xc1pL\xee\x01\x1b\xe3\xbc\x92OE,Nj\xf9\xac\x9d\x87\xb7\xbb;'\xeae\xc9\xef\xfe_9@\xa9,\x85}\xb7\xab\x13\xbfw\x1b\x8eg\xab\xc8\x08\x88\x08"}]}, 'ttl': 1695832907, 'signature': b'', '@type': 'dht.value'}}

    # choose node
    node = resp['value']['value']['nodes'][1]

    pub_k = bytes.fromhex(node['id']['key'])
    adnl_addr = Server('', 0, pub_key=pub_k).get_key_id()
    resp = await client.find_value(key=client.get_dht_key_id(id_=adnl_addr), timeout=20)  # find overlay node
    print(resp)
    # {'@type': 'dht.valueFound', 'value': {'key': {'key': {'id': 'a63ece1e9dabe9348711339998a423553e9899fdd9c3e2ca6942686e7f4e34f6', 'name': b'address', 'idx': 0, '@type': 'dht.key'}, 'id': {'key': '6aa8baa5d300a70a83d901028842c8f1ff7244d6ff12c33faf08265949f7ca1d', '@type': 'pub.ed25519'}, 'update_rule': {'@type': 'dht.updateRule.signature'}, 'signature': b'P\x12\xcbWu9\xef\xf48\xd2\n\xb5\xb0\xc9\xa0\xfaLo\xc6\xbc\x96\xc8)I\xaa\x0e\xfcm\x1b\xf2jf\xea\xbe\xf4Gb\xcc!L\x9c9\xeb{\x13\xcd\x8c2<\xc7\xe5\x9cbxr\x80\xe4\xe0\xc7\xa4\xb7\xed\x01\x03', '@type': 'dht.keyDescription'}, 'value': {'@type': 'adnl.addressList', 'addrs': [{'@type': 'adnl.address.udp', 'ip': -1923101371, 'port': 30303}], 'version': 1695828878, 'reinit_date': 1695314720, 'priority': 0, 'expire_at': 0}, 'ttl': 1695832478, 'signature': b'.\xff\xed\x0brf\x13\x13\x8b\xf3\xb6\x85\xaaQ7dH\r\xbaq8m\x14\xf8?\xc7\xb0sJ!\x87@!*\xcd\x80{Y\x92\x17\xfd\xa3\x18fb\x8aD\xe2b``\xb5\xb7\x03u\xa3\xbe\x83\xdd\x9c\xf9\x1f,\x02', '@type': 'dht.value'}}


if __name__ == '__main__':
    asyncio.run(main())
