import typing

from pytoniq_core.tl import BlockIdExt

from .overlay import OverlayTransport, OverlayNode
from .overlay_manager import OverlayManager
from .broadcast import BroadcastSimple
from .fec_broadcast import create_fec_broadcast


class ShardOverlay:

    def __init__(
            self,
            overlay_manager: OverlayManager,
            external_messages_handler: typing.Callable = None,
            blocks_handler: typing.Callable = None,
            shard_blocks_handler: typing.Callable = None,
    ):
        self._overlay: OverlayTransport = overlay_manager.overlay
        self._manager = overlay_manager
        self.external_messages_disabled = False
        self.external_messages_handler = external_messages_handler  # todo: we can emulate externals, but need to store state
        self.blocks_handler = blocks_handler  # todo: we can check blocks via key blocks and validator signatures
        self.shard_blocks_handler = shard_blocks_handler
        self.init_handlers()

    def init_handlers(self):
        if self.external_messages_handler is not None:
            self._overlay.set_broadcast_handler('tonNode.externalMessageBroadcast', self.external_messages_handler)
        if self.blocks_handler is not None:
            self._overlay.set_broadcast_handler('tonNode.newShardBlockBroadcast', self.shard_blocks_handler)
            self._overlay.set_broadcast_handler('tonNode.blockBroadcast', self.blocks_handler)

    async def send_external_message(self, message: bytes):
        data = {'@type': 'tonNode.externalMessageBroadcast', 'message': {
            'data': message,
            '@type': 'tonNode.externalMessage'}}
        query = self._overlay.schemas.serialize('tonNode.externalMessageBroadcast', data)
        if len(query) < self._overlay.max_simple_broadcast_size:
            b = BroadcastSimple.create(self._overlay, query, 0)
            await b.run()
        else:
            await create_fec_broadcast(self._overlay, query, 1)

    async def raw_download_block(self, block: BlockIdExt, peer: OverlayNode) -> bytes:
        """
        :param block:
        :param peer:
        :return: block boc
        """
        return (await self._overlay.send_query_message(tl_schema_name='tonNode.downloadBlock',
                                              data={'block': block.to_dict()}, peer=peer))[0]

    async def prepare_block(self, block: BlockIdExt, peer: OverlayNode) -> dict:
        return (await self._overlay.send_query_message(tl_schema_name='tonNode.prepareBlock',
                                              data={'block': block.to_dict()}, peer=peer))[0]
