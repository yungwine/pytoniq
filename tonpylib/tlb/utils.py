import typing

from .tlb import TlbScheme, TlbError
from ..boc import Slice, Cell, CellTypes


class MerkleUpdate(TlbScheme):
    """
    !merkle_update#02 {X:Type} old_hash:bits256 new_hash:bits256 old:^X new:^X = MERKLE_UPDATE X;
    """

    def __init__(self, cell: Cell, old_hash: bytes, new_hash: bytes, old, new):
        self.cell = cell
        self.old_hash = old_hash
        self.new_hash = new_hash
        self.old = old
        self.new = new

    @classmethod
    def serialize(cls, *args): ...

    @classmethod
    def deserialize(cls, cell: Cell, deserializer: typing.Callable) -> typing.Optional["MerkleUpdate"]:
        if cell.type_ != CellTypes.merkle_update:
            return None

        cell_slice = cell.begin_parse()
        tag = cell_slice.load_bytes(1)[:1]
        # if tag != b'\x02':
        #     raise TlbError(f'MerkleUpdate deserialization error: unexpected tag {tag}')
        old_hash = cell_slice.load_bytes(32)
        new_hash = cell_slice.load_bytes(32)
        old = deserializer(cell_slice.load_ref().begin_parse())
        new = deserializer(cell_slice.load_ref().begin_parse())
        return cls(cell, old_hash, new_hash, old, new)


class HashUpdate(TlbScheme):
    """
    update_hashes#72 {X:Type} old_hash:bits256 new_hash:bits256 = HASH_UPDATE X;
    """

    def __init__(self, old_hash: bytes, new_hash: bytes):
        self.old_hash = old_hash
        self.new_hash = new_hash

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_bytes(1)[:1]
        if tag != b'r':
            raise TlbError(f'HashUpdate deserialization error: unexpected tag {tag}')
        old_hash = cell_slice.load_bytes(32)
        new_hash = cell_slice.load_bytes(32)
        return cls(old_hash, new_hash)


def deserialize_shard_hashes(cell_slice: Slice):
    from .block import BinTree, ShardDescr
    shard_hashes = cell_slice.load_dict(32, value_deserializer=lambda src: BinTree.deserialize(
        src.load_ref().begin_parse()))
    if shard_hashes:
        for k in shard_hashes:
            for i in range(len(shard_hashes[k].list)):
                shard_hashes[k].list[i] = ShardDescr.deserialize(shard_hashes[k].list[i])
    return shard_hashes
