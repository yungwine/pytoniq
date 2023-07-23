import os
import time
import typing

from ..tl.block import BlockIdExt


async def sync(client: "LiteClient", to_block: BlockIdExt, init_block: BlockIdExt):
    from .client import LiteClient
    client: LiteClient
    blocks_data = get_last_stored_blocks()
    if not blocks_data:
        mc_block = init_block
        key_block = init_block
    else:
        ttl, key_block, mc_block = parse_blocks(blocks_data)
        if ttl <= time.time():
            mc_block = init_block
            key_block = init_block
    """
    Looks like last mc block should be be much sooner than last synced key block
    (cause we store key blocks with big ttl), but the lite node doesnt have to store any blocks except key blocks which
    persistent state has not expired.
    So the best solution is to ask liteserver if it remembers stored mc block and if not sync from the key block (or even init). 
    """
    try:
        best_key, best_key_ts = await client.get_mc_block_proof(known_block=mc_block, target_block=to_block, return_best_key_block=True)
    except:  # TODO specify exception class
        best_key, best_key_ts = await client.get_mc_block_proof(known_block=key_block, target_block=to_block, return_best_key_block=True)
    client.last_key_block = best_key
    mc_block = await client.get_trusted_last_mc_block()
    key_ttl = persistent_state_ttl(best_key_ts)
    store_blocks(blocks_to_bytes(key_ttl, best_key, mc_block), True, best_key)
    return True


def get_block_store_path():
    dir = os.path.join(os.path.curdir, '.blockstore')
    path = os.path.normpath(dir)
    if not os.path.isdir(path):
        os.mkdir(path)
    return path


def get_last_stored_blocks() -> typing.Optional[bytes]:
    path = get_block_store_path()
    files = []
    for f in os.listdir(path):
        files.append(f)
    if not len(files):
        return None
    with open(os.path.join(path, files[-1]), 'rb') as f:
        result = f.read()
    return result


def store_blocks(data: bytes, delete_old: bool = True, key: BlockIdExt = None):
    path = get_block_store_path()
    if delete_old:
        for f in os.listdir(path):
            if key:
                if key.root_hash.hex() in f:
                    os.remove(os.path.join(path, f))
                    print(f)
    file_name = data[:84].hex() + '.blks'
    print(file_name)
    with open(os.path.join(path, file_name), 'wb') as f:
        f.write(data)
    return


def parse_blocks(data: bytes) -> typing.Tuple[int, BlockIdExt, BlockIdExt]:
    ttl = int.from_bytes(data[:4], 'big', signed=False)
    last_trusted_key_block = BlockIdExt.from_bytes(data[4:84])
    last_trusted_mc_block = BlockIdExt.from_bytes(data[84:])
    return ttl, last_trusted_key_block, last_trusted_mc_block


def blocks_to_bytes(ttl: int, last_trusted_key_block: BlockIdExt, last_trusted_mc_block: BlockIdExt):
    return ttl.to_bytes(4, 'big', signed=False) + last_trusted_key_block.to_bytes() + last_trusted_mc_block.to_bytes()


def count_trailing_zeros(x: int):
    return (x & -x).bit_length() - 1


def persistent_state_ttl(ts: int):
    # https://github.com/ton-blockchain/ton/blob/d2b418bb703ed6ccd89b7d40f9f1e44686012014/validator/interfaces/validator-manager.h#L176
    x = ts / (1 << 17)
    assert x > 0
    b = count_trailing_zeros(int(x))
    return ts + ((1 << 18) << b)


def choose_key_block(blk: BlockIdExt, blk_ts: int, other_blk: typing.Optional[BlockIdExt], other_ts: typing.Optional[int]):
    if other_blk is None:
        return blk, blk_ts
    if blk is None:
        return other_blk, other_ts
    print(blk, blk_ts, other_blk, other_ts)
    p1 = persistent_state_ttl(blk_ts)
    p2 = persistent_state_ttl(other_ts)
    c_t = time.time()
    if p1 < c_t < p2:
        return other_blk, other_ts
    if p2 < c_t < p1:
        return blk, blk_ts

    # p1 and p2 > time.time
    d1 = c_t - p1
    d2 = c_t - p2

    min_time = 21 * 3600 * 24  # 3 weeks

    if d2 >= min_time and other_blk.seqno > blk.seqno:
        return other_blk, other_ts
    elif d2 < min_time and other_blk.seqno > blk.seqno:
        if d1 >= min_time:
            return blk, blk_ts
        else:
            return other_blk, other_ts
    else:
        return blk, blk_ts


# 'fe39a8dbfe762ae0a471f1a703000000ffffffff17a3a92992aabea785a7a090985a265cd31f323d849da51239737e321fb055695e994fcf4d425c0a6ce6a792594b7173205f740a39cd56f537defd28b48a0f6effffffff00000000000000808e7fb201cc25ea65a5f061f04b194e2a0b1f98e319fefdbdc1cd8a9c9399b48ff7b8759d0f410a036ca55cb1fc8f0419c6bb70171eaf06d8159f21189e063df0e2d1d7d0ffffffff0000000000000080a585b2017c1f9d924340a6359c98aaf49b6df190d3347fafeb5265f4a82c0e40aa5e5b0f14258afa4576e33d44ca411b70f17398bf43ac8441fc3cedd73b77c1ccbb30814949286400000000ffffffff00000000000000800e63a70161192b72664cbcb06f8da9f0282c8bdf0e2871e18fb457e0c7cca6d502822bfe378db1ccf9c98c3944de1c4f5ce6fea4dcd7a26811b695f9019ccc3e7200e35b01000000'
