import asyncio
from types import coroutine

from pytoniq_core.tlb.block import ExtBlkRef

from pytoniq.liteclient import LiteClient
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

    async def run(self, mc_seqno: int = None):
        if not self.client.inited:
            raise Exception('should init client first')

        if mc_seqno is None:
            master_blk: BlockIdExt = self.mc_info_to_tl_blk(await self.client.get_masterchain_info())
        else:
            master_blk, _ = await self.client.lookup_block(wc=-1, shard=-9223372036854775808, seqno=mc_seqno)

        master_blk_prev, _ = await self.client.lookup_block(wc=-1, shard=-9223372036854775808, seqno=master_blk.seqno - 1)

        shards_prev = await self.client.get_all_shards_info(master_blk_prev)
        for shard in shards_prev:
            self.shards_storage[self.get_shard_id(shard)] = shard.seqno

        while True:
            await self.blks_queue.put(master_blk)

            shards = await self.client.get_all_shards_info(master_blk)
            for shard in shards:
                await self.get_not_seen_shards(shard)
                self.shards_storage[self.get_shard_id(shard)] = shard.seqno

            while not self.blks_queue.empty():
                await self.block_handler(self.blks_queue.get_nowait())

            while True:
                if master_blk.seqno + 1 == self.client.last_mc_block.seqno:
                    master_blk = self.client.last_mc_block
                    break
                elif master_blk.seqno + 1 < self.client.last_mc_block.seqno:
                    master_blk, _ = await self.client.lookup_block(wc=-1, shard=-9223372036854775808, seqno=master_blk.seqno + 1)
                    break
                await asyncio.sleep(0.1)

    async def get_not_seen_shards(self, shard: BlockIdExt):
        if self.shards_storage.get(self.get_shard_id(shard)) == shard.seqno:
            return

        full_blk = await self.client.raw_get_block_header(shard)
        prev_ref = full_blk.info.prev_ref
        if prev_ref.type_ == 'prev_blk_info':  # only one prev block
            prev: ExtBlkRef = prev_ref.prev
            prev_shard = self.get_parent_shard(shard.shard) if full_blk.info.after_split else shard.shard
            await self.get_not_seen_shards(BlockIdExt(
                    workchain=shard.workchain, seqno=prev.seqno, shard=prev_shard,
                    root_hash=prev.root_hash, file_hash=prev.file_hash
                )
            )
        else:
            prev1: ExtBlkRef = prev_ref.prev1
            prev2: ExtBlkRef = prev_ref.prev2
            await self.get_not_seen_shards(BlockIdExt(
                    workchain=shard.workchain, seqno=prev1.seqno, shard=self.get_child_shard(shard.shard, left=True),
                    root_hash=prev1.root_hash, file_hash=prev1.file_hash
                )
            )
            await self.get_not_seen_shards(BlockIdExt(
                    workchain=shard.workchain, seqno=prev2.seqno, shard=self.get_child_shard(shard.shard, left=False),
                    root_hash=prev2.root_hash, file_hash=prev2.file_hash
                )
            )

        await self.blks_queue.put(shard)

    def get_child_shard(self, shard: int, left: bool) -> int:
        x = self.lower_bit64(shard) >> 1
        if left:
            return self.simulate_overflow(shard - x)
        return self.simulate_overflow(shard + x)

    def get_parent_shard(self, shard: int) -> int:
        x = self.lower_bit64(shard)
        return self.simulate_overflow((shard - x) | (x << 1))

    @staticmethod
    def simulate_overflow(x) -> int:
        return (x + 2**63) % 2**64 - 2**63

    @staticmethod
    def lower_bit64(num: int) -> int:
        return num & (~num + 1)

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
    print(f"{len(transactions)=}")
    # for transaction in transactions:
    #     print(transaction.in_msg)


client = LiteClient.from_mainnet_config(ls_i=14, trust_level=2, timeout=20)


async def main():

    await client.connect()
    await client.reconnect()
    await BlockScanner(client=client, block_handler=handle_block).run()


if __name__ == '__main__':
    asyncio.run(main())
