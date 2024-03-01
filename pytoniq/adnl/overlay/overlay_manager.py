import logging
import asyncio

from pytoniq_core.crypto.ciphers import Server

from .overlay import OverlayTransport, OverlayNode


def process_get_random_peers_request(_, overlay_client: OverlayTransport):
    known_peers = overlay_client.get_neighbours(5)
    peers = [overlay_client.get_signed_myself()]
    for peer in known_peers:
        if peer.to_tl():
            peers.append(peer.to_tl())
    return {
        '@type': 'overlay.nodes',
        'nodes': peers
    }


def process_get_capabilities_request(_):
    return {
        '@type': 'tonNode.capabilities',
        'version': 2,
        'capabilities': 2,
    }


class OverlayManager:

    def __init__(self, overlay: OverlayTransport, dht_client, max_peers: int = 30):
        from ..dht import DhtClient
        self.overlay = overlay
        self.dht: DhtClient = dht_client
        self.max_peers = max_peers
        self.logger = logging.getLogger(self.__class__.__name__)
        self.init_handlers()

    def init_handlers(self):
        self.overlay.set_query_handler(type_='overlay.getRandomPeers',
                                        handler=lambda i: process_get_random_peers_request(i, self.overlay))
        self.overlay.set_query_handler(type_='tonNode.getCapabilities',
                                        handler=lambda i: process_get_capabilities_request(i))

    async def start(self):
        if not self.overlay.inited:
            await self.overlay.start()
        self.overlay.loop.create_task(self.get_more_peers())

    async def get_more_peers(self):
        while True:
            if len(self.overlay.peers) == 0:
                self.logger.debug('Getting first peers! This may take some time')
                try:
                    nodes = await self.dht.get_overlay_nodes(self.overlay.overlay_id, self.overlay)
                except asyncio.TimeoutError:
                    nodes = []
                for node in nodes:
                    node: OverlayNode
                    if node is None:
                        continue
                    try:
                        await asyncio.wait_for(node.connect(), 1.5)
                        self.logger.debug(f'Connected to peer {node.key_id.hex()}')
                    except asyncio.TimeoutError:
                        continue
                self.logger.debug(f'Got {len(self.overlay.peers)} first peers')
                await asyncio.sleep(10)
                continue
            clients = []
            tasks = []
            for _, peer in list(self.overlay.peers.items()):
                if len(self.overlay.peers) > self.max_peers:
                    return 0
                self.logger.debug(f'getting nodes from peer {peer.get_key_id().hex()}')
                if not peer.connected:
                    self.logger.debug(f'peer {peer.get_key_id().hex()} is already not connected')
                    continue
                tasks.append(self.overlay.get_random_peers(peer))
            result = await asyncio.gather(*tasks, return_exceptions=True)
            tasks = []
            for resp in result:
                if isinstance(resp, Exception):
                    continue
                self.logger.debug(f"got {len(resp[0]['nodes'])} from peer")
                for node in resp[0]['nodes']:
                    pub_k = bytes.fromhex(node['id']['key'])
                    adnl_addr = Server('', 0, pub_key=pub_k).get_key_id()
                    if adnl_addr not in self.overlay.peers:
                        tasks.append(self.dht.get_overlay_node(node, self.overlay))
                        # new_client = await dht_client.get_overlay_node(node, overlay)
                        # if new_client is not None:
                        #     clients.append(new_client)
            result = await asyncio.gather(*tasks, return_exceptions=True)

            for new_client in result:
                if isinstance(new_client, (Exception, BaseException)):
                    continue
                if new_client is not None:
                    clients.append(new_client)

            async def try_connect(client):
                try:
                    await client.connect()
                    return True
                except asyncio.TimeoutError:
                    return False

            tasks = []
            for new_client in clients:
                if len(self.overlay.peers) > self.max_peers:
                    break
                if new_client is not None:
                    tasks.append(try_connect(new_client))
            result = await asyncio.gather(*tasks, return_exceptions=True)
            self.logger.debug(f'Got {sum([1 for r in result if r is True])} more peers')
            await asyncio.sleep(10)
