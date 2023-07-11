"""
This is quite an advanced level, so it is highly recommended that you first become familiar with https://docs.ton.org/tvm.pdf 3.1.2 - 3.1.7
"""
import typing
from ..tl.block import BlockId, BlockIdExt

# from .cell import Cell
from .tvm_bitarray import TvmBitarray


class CellTypes:
    ordinary = -1
    pruned_branch = 1
    library_ref = 2
    merkle_proof = 3
    merkle_update = 4


class LevelMask:
    # https://github.com/xssnick/tonutils-go/blob/master/tvm/cell/level.go#L17
    def __init__(self, m: int):
        self._m = m
        self._level = self.get_level()
        self._hash_index = self.get_hash_index()

    @property
    def mask(self):
        return self._m

    @property
    def level(self):
        return self._level

    @property
    def hash_index(self):
        return self._hash_index

    def get_level(self):
        return self._m.bit_length()

    def get_hash_index(self):
        return self._m.bit_count()

    def apply(self, level: int):
        return LevelMask(self._m & ((1 << level) - 1))

    def is_significant(self, level: int):
        return level == 0 or (self._m >> (level - 1)) % 2 != 0


class ProofError(BaseException):
    pass


def check_proof(cell: "Cell", hash_: bytes) -> None:
    if cell.type_ != CellTypes.merkle_proof:
        raise ProofError(f'Expected Merkle proof Cell, got {cell.type_} Cell type')

    if cell.data[1:33] != hash_:
        raise ProofError('Provided invalid hash')

    if cell[0].get_hash(0) != hash_:  # TODO Level mask
        raise ProofError('Merkle proof is invalid')

    return


# https://github.com/ton-blockchain/ton/blob/master/crypto/block/check-proof.cpp
def check_block_header_proof(root_cell: "Cell", block_hash: bytes, store_state_hash=False):
    root_hash = root_cell.get_hash(0)
    if root_hash != block_hash:
        raise ProofError('Block header proof error: hashes unmatch')
    if store_state_hash:
        state_update = root_cell[2][1]
        return state_update.get_hash(0)
    return


def check_shard_proof(shard_proof: bytes, blk: BlockIdExt, shrd_blk: BlockIdExt):
    from .cell import Cell
    from ..tlb.block import Block, ShardStateUnsplit

    if blk.root_hash == shrd_blk.root_hash:
        return
    if blk.workchain != -1:
        raise ProofError('expected masterchain block')
    shard_proof_cells = Cell.from_boc(shard_proof)

    if len(shard_proof_cells) != 2:
        raise ProofError('expected 2 root cells in shard proof')

    mc_block_cell = shard_proof_cells[0]
    mc_state_root = shard_proof_cells[1]

    block_info = Block.deserialize(mc_block_cell[0].begin_parse()).info

    if not (block_info.seqno == blk.seqno and block_info.shard.workchain_id == blk.workchain):
        raise ProofError('block info mismatch')

    mc_state_hash = mc_state_root[0].get_hash(0)
    state_hash = check_block_header_proof(mc_block_cell[0], blk.root_hash, True)

    if mc_state_hash != state_hash:
        raise ProofError('mc state hashes mismatch')

    shard = ShardStateUnsplit.deserialize(mc_state_root[0].begin_parse())

    shard_dict = shard.custom.shard_hashes

    shard_descr = shard_dict.get(shrd_blk.workchain)
    if shard_descr is None:
        raise ProofError('cannot find shard block in ShardHashes')

    # shard_dict looks like this:
    # {0: {'list': [{'seq_no': 36667578, 'reg_mc_seqno': 30985767, 'start_lt': 39143950000000, 'end_lt': 39143950000004, 'root_hash': b'\x83f\xe4P\x05\xf3\xbe\x83\xaf\x00\xf9\xbf\xde\x01\x9e=fF%\xd4\xed&\xb9\x0b\xd4\n\xb1]K\xedd9', 'file_hash': b"n\xdd\xdb\xc8\xb01\xbe\xcf\xf7\xed\xb0'3\x9b\t\xe7\xd7J\xac/\x14W!y\x82o\xf6\x19\xeb\xeaj\xae", 'before_split': False, 'before_merge': False, 'want_split': False, 'want_merge': True, 'nx_cc_updated': False, 'flags': 0, 'next_catchain_seqno': 456373, 'next_validator_shard': 9223372036854775808, 'min_ref_mc_seqno': 30985764, 'gen_utime': 1688896742, 'split_merge_at': None, 'fees_collected': {'grams': 1006293421, 'other': {'dict': None}}, 'funds_created': {'grams': 1000000000, 'other': {'dict': None}}}]}}

    shard_descr = shard_descr.list[0]  # see BinTree TLB schema

    if shard_descr.root_hash != shrd_blk.root_hash:
        raise ProofError('shard block actual and expected hashes mismatch')

    return


def check_account_proof(proof: bytes, shrd_blk: BlockIdExt, address: "Address", account_state_root: "Cell", return_account_descr: bool = False):
    from .cell import Cell
    from ..tlb.block import ShardStateUnsplit

    proof_cells = Cell.from_boc(proof)
    if len(proof_cells) != 2:
        raise ProofError('expected 2 root cells in account state proof')

    state_cell = proof_cells[1]  # merkle proof type Cell

    state_hash = check_block_header_proof(proof_cells[0][0], shrd_blk.root_hash, True)

    if state_cell[0].get_hash(0) != state_hash:
        raise ProofError('state hashes mismatch')

    shard = ShardStateUnsplit.deserialize(state_cell[0].begin_parse())

    shard_account = shard.accounts[0][int.from_bytes(address.hash_part, 'big')]

    account_state_root_proved = shard_account.cell

    if account_state_root_proved[0].get_hash(0) != account_state_root.get_hash(0):
        raise ProofError('account state proof invalid')

    if return_account_descr:
        return shard_account

    return
