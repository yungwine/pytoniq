import asyncio
import datetime
import logging
import time
import typing
from types import coroutine

from pytoniq_core.tlb.block import ExtBlkRef

from pytoniq.liteclient import LiteClient
from pytoniq_core.tlb import Block, ValueFlow, ShardAccounts
from pytoniq_core.tl import BlockIdExt


class BlockScanner:

    def __init__(self,
                 client: LiteClient,
                 block_handler: coroutine
                 ):
        """
        :param client: LiteClient
        :param block_handler: function to be called on new block
        """
        self.client = client
        self.block_handler = block_handler
        self.shards_storage = {}
        self.blks_queue = asyncio.Queue()

    async def run(self):
        if not self.client.inited:
            raise Exception('should init client first')
        master_blk = self.mc_info_to_tl_blk(await self.client.get_masterchain_info())
        shards = await self.client.get_all_shards_info(master_blk)
        for shard in shards:
            self.shards_storage[self.get_shard_id(shard)] = shard.seqno
            await self.blks_queue.put(shard)

        while True:
            await self.blks_queue.put(master_blk)

            shards = await self.client.get_all_shards_info(master_blk)
            for shard in shards:
                await self.get_not_seen_shards(shard)
                self.shards_storage[self.get_shard_id(shard)] = shard.seqno

            while not self.blks_queue.empty():
                await self.block_handler(self.blks_queue.get_nowait())

            master_blk = self.mc_info_to_tl_blk(
                await self.client.wait_masterchain_seqno(
                    seqno=master_blk.seqno + 1, timeout_ms=10000, schema_name='getMasterchainInfo', data={}
                )
            )

    async def get_not_seen_shards(self, shard: BlockIdExt):
        if self.shards_storage.get(self.get_shard_id(shard)) == shard.seqno:
            return []
        result = []
        await self.blks_queue.put(shard)
        full_blk = await self.client.raw_get_block_header(shard)
        prev_ref = full_blk.info.prev_ref
        if prev_ref.type_ == 'prev_blk_info':  # only one prev block
            prev: ExtBlkRef = prev_ref.prev
            await self.get_not_seen_shards(BlockIdExt(
                    workchain=shard.workchain, seqno=prev.seqno, shard=shard.shard,
                    root_hash=prev.root_hash, file_hash=prev.file_hash
                )
            )
        else:
            prev1: ExtBlkRef = prev_ref.prev1
            prev2: ExtBlkRef = prev_ref.prev2
            await self.get_not_seen_shards(BlockIdExt(
                    workchain=shard.workchain, seqno=prev1.seqno, shard=shard.shard,
                    root_hash=prev1.root_hash, file_hash=prev1.file_hash
                )
            )
            await self.get_not_seen_shards(BlockIdExt(
                    workchain=shard.workchain, seqno=prev2.seqno, shard=shard.shard,
                    root_hash=prev2.root_hash, file_hash=prev2.file_hash
                )
            )
        return result

    @staticmethod
    def mc_info_to_tl_blk(info: dict):
        return BlockIdExt.from_dict(info['last'])

    @staticmethod
    def get_shard_id(blk: BlockIdExt):
        return f'{blk.workchain}:{blk.shard}'


async def handle_block(block: BlockIdExt):
    if block.workchain == -1:  # skip masterchain blocks
        return
    print(block)
    transactions = await client.raw_get_block_transactions_ext(block)
    for transaction in transactions:
        print(transaction.in_msg)


client = LiteClient.from_mainnet_config(ls_i=14, trust_level=2, timeout=20)


async def main():

    await client.connect()
    await client.reconnect()
    await BlockScanner(client=client, block_handler=handle_block).run()


if __name__ == '__main__':
    asyncio.run(main())
