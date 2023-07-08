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
        old_hash = cell_slice.load_bytes(32)
        new_hash = cell_slice.load_bytes(32)
        old = deserializer(cell_slice.load_ref().begin_parse())
        new = deserializer(cell_slice.load_ref().begin_parse())

        return cls(cell, old_hash, new_hash, old, new)
