import logging
import os
import time
import typing

from pytoniq_core.tl.block import BlockIdExt


logger = logging.getLogger('sync')


async def sync(client, to_block: BlockIdExt, init_block: BlockIdExt):
    logger.info(msg=f'syncing to {to_block}')
    from .client import LiteClient
    client: LiteClient
    valid_key_block_stored = False
    blocks_data = get_last_stored_blocks(init_block.root_hash.hex())
    if not blocks_data:
        logger.debug(f'no last blocks were found, syncing from the init block {init_block}')
        mc_block = init_block
        key_block = init_block
    else:
        ttl, key_ts, key_block, mc_block = parse_blocks(blocks_data)
        logger.debug(f'found key block with ttl {ttl}')
        valid_key_block_stored = True
        if ttl <= time.time():
            logger.debug(f'key block ttl has been expired, syncing from the init block {init_block}')
            mc_block = init_block
            key_block = init_block
            valid_key_block_stored = False

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

    if valid_key_block_stored:
        best_key, best_key_ts = choose_key_block(key_block, key_ts, best_key, best_key_ts)

    key_ttl = persistent_state_ttl(best_key_ts)
    logger.info(msg=f'synced! store key block {best_key} with ttl {key_ttl}')

    store_blocks(blocks_to_bytes(key_ttl, best_key_ts, best_key, to_block), True, init_block.root_hash.hex())
    return True


def get_block_store_path():
    dir = os.path.join(os.path.curdir, '.blockstore')
    path = os.path.normpath(dir)
    if not os.path.isdir(path):
        os.mkdir(path)
    return path


def get_last_stored_blocks(init_block_hash: str) -> typing.Optional[bytes]:
    path = get_block_store_path()
    files = []
    for f in os.listdir(path):
        if init_block_hash in f:
            files.append(f)
    if not len(files):
        return None
    with open(os.path.join(path, files[-1]), 'rb') as f:
        result = f.read()
    return result


def store_blocks(data: bytes, delete_old: bool = True, init_block_hash: str = None):
    path = get_block_store_path()
    if delete_old:
        for f in os.listdir(path):
            deleted = False
            if init_block_hash:
                if init_block_hash in f:
                    os.remove(os.path.join(path, f))
                    deleted = True
            if not deleted:
                ttl = int(f[:8], 16)
                if ttl < time.time():
                    os.remove(os.path.join(path, f))
    file_name = data[:88].hex() + init_block_hash + '.blks'
    with open(os.path.join(path, file_name), 'wb') as f:
        f.write(data)
    return


def parse_blocks(data: bytes) -> typing.Tuple[int, int, BlockIdExt, BlockIdExt]:
    ttl = int.from_bytes(data[:4], 'big', signed=False)
    ts = int.from_bytes(data[4:8], 'big', signed=False)
    last_trusted_key_block = BlockIdExt.from_bytes(data[8:88])
    last_trusted_mc_block = BlockIdExt.from_bytes(data[88:])
    return ttl, ts, last_trusted_key_block, last_trusted_mc_block


def blocks_to_bytes(ttl: int, ts: int, last_trusted_key_block: BlockIdExt, last_trusted_mc_block: BlockIdExt):
    return ttl.to_bytes(4, 'big', signed=False) + ts.to_bytes(4, 'big', signed=False) + last_trusted_key_block.to_bytes() + last_trusted_mc_block.to_bytes()


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
    p1 = persistent_state_ttl(blk_ts)
    p2 = persistent_state_ttl(other_ts)
    c_t = time.time()
    if p1 < c_t and p2 < c_t:
        if blk.seqno > other_blk.seqno:
            return blk, blk_ts
        else:
            return other_blk, other_ts
    if p1 < c_t:
        return other_blk, other_ts
    if p2 < c_t:
        return blk, blk_ts

    d1 = p1 - c_t
    d2 = p2 - c_t

    min_time = 21 * 3600 * 24  # 3 weeks
    if d1 >= min_time:
        if d2 < min_time:
            return blk, blk_ts
        else:
            if blk.seqno > other_blk.seqno:
                return blk, blk_ts
            else:
                return other_blk, other_ts
    elif d2 >= min_time:
        return other_blk, other_ts
    else:
        if blk.seqno > other_blk.seqno:
            return blk, blk_ts
        return other_blk, other_ts
