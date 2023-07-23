import hashlib
import typing


from ..tlb.block import Block, ShardStateUnsplit
from ..tlb.config import ValidatorDescr, CatchainConfig, ValidatorSet
from ..tl.block import BlockId, BlockIdExt
from ..crypto.signature import verify_sign
from ..boc.tvm_bitarray import TvmBitarray
from ..boc.exotic import CellTypes
from ..boc.cell import Cell
from ..boc.address import Address


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

    if blk == shrd_blk:
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

    return shard_descr


def check_account_proof(proof: bytes, shrd_blk: BlockIdExt, address: "Address", account_state_root: "Cell", return_account_descr: bool = False):

    proof_cells = Cell.from_boc(proof)
    if len(proof_cells) != 2:
        raise ProofError('expected 2 root cells in account state proof')

    state_cell = proof_cells[1]

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


def calculate_node_id_short(pub_key: bytes):
    return hashlib.sha256(b'\xc6\xb4\x13H' + pub_key).digest()


def check_block_signatures(nodes: typing.List[ValidatorDescr], signatures: typing.List[dict], blk: BlockIdExt):
    from ..tlb.config import ValidatorDescr

    node_map = {}

    total_weight = 0
    signed_weight = 0
    i = 0
    for node in nodes:
        total_weight += node.weight
        i += 1

        node_map[calculate_node_id_short(node.public_key.pubkey)] = node

    to_sign = b'pn\x0b\xc5' + blk.root_hash + blk.file_hash  # bytes.fromhex('c50b6e70')[::-1] - magic
    i = 0
    for sig in signatures:
        node = node_map.get(bytes.fromhex(sig['node_id_short']))
        node: ValidatorDescr
        i += 1

        if node is None:
            raise ProofError('cannot find node_id_short in validator list')

        result = verify_sign(public_key=node.public_key.pubkey, signed_message=to_sign, signature=sig['signature'])

        if not result:
            raise ProofError('invalid signature!')

        signed_weight += node.weight

    if signed_weight * 3 >= total_weight * 2:  # >= 2/3
        return

    raise ProofError(f'Block {blk} has not been signed by 2/3 of validators')


def compute_validator_set(ccv_conf: CatchainConfig, blk: BlockIdExt, vset: ValidatorSet, cc_seqno: int = None):
    is_mc = blk.workchain == -1

    if is_mc:
        count = vset.main
    else:
        count = ccv_conf.shard_validators_num
    count = min(count, vset.total)

    if is_mc:
        if ccv_conf.shuffle_mc_validators:
            # TODO
            pass
        return list(vset.list.values())[:count]
    # TODO true algorithm
    nodes = []
    for i in range(count):
        node = vset.list[i + vset.total]
        node.weight = 1  # shardchain validator lists have all weights = 1 ?
        nodes.append(node)
    return nodes
