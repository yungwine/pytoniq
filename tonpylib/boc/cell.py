import hashlib
import typing

from bitarray.util import ba2int

from .deserialize import Boc, NullCell
from .tvm_bitarray import TvmBitarray, bitarray, BitarrayLike
from .utils import bytes_to_uint
from ..crypto.crc import crc32c


class CellError(BaseException):
    pass


class Cell(NullCell):
    """
    Cell in tonpy is immutable type.
    If you want to read from cell use .begin_parse() method.
    If you want to write to cell use .to_builder() method.

    tonpy's Cell serialization is 20 times faster than tonsdk's Cell.
    But for convenience you can initialize this Cell from tonsdk's one or convert this Cell to tonsdk's one.
    """
    def __init__(self, bits: BitarrayLike, refs: typing.List["Cell"], cell_type: int = -1) -> None:
        self.bits: BitarrayLike = bits
        self.refs: list = refs
        self.type_: int = cell_type
        self.is_exotic: bool = cell_type != -1
        super().__init__(bits, refs, cell_type)

        """ fast but takes a lot of memory"""
        self._descriptors: bytes = self.get_descriptors()
        self._data_bytes: bytes = self.get_data_bytes()
        self._cell_repr: bytes = self.get_representation()
        self._hash: bytes = self.compute_hash()

    def to_builder(self):
        from .builder import Builder
        return Builder().store_cell(self)

    def get_level(self) -> int:
        return 0
        ...
        for ref in self.refs:
            ...

    def get_refs_descriptor(self) -> bytes:
        # d1 = r + 8s + 32l
        d1 = len(self.refs) + 8 * self.is_exotic + 32 * self.get_level()
        return d1.to_bytes(1, 'big')

    def get_bits_descriptor(self) -> bytes:
        # d2 = ceil(b/8) + floor(b/8)
        bit_len = len(self.bits)
        d2 = (bit_len // 8) * 2
        d2 += 1 if bit_len % 8 else 0
        return d2.to_bytes(1, 'big')

    def get_descriptors(self) -> bytes:
        return self.get_refs_descriptor() + self.get_bits_descriptor()

    def get_depth(self) -> int:
        # https://github.com/igroman787/mytonlib/blob/master/mytonlib/mytypes.py#L153
        depths = [0]
        for ref in self.refs:
            depths.append(ref.get_depth() + 1)
        return max(depths)

    def get_data_bytes(self) -> bytes:
        if isinstance(self.bits, TvmBitarray):
            #  cause we have max size in TvmBitarray
            result = self.bits.to_bitarray()
        else:
            result = self.bits
        if len(result) % 8:
            result.append(1)
            result.fill()
        return result.tobytes()

    def get_representation(self) -> bytes:
        # CellRepr(c) = CellRepr∞ (c) = d1d2 + data + (depth(r_i) + hash(r_i) for all i)
        descs = self._descriptors
        data = self._data_bytes
        result = descs + data
        for ref in self.refs:
            result += ref.get_depth().to_bytes(2, 'big') + ref.hash
        return result

    @property
    def hash(self) -> bytes:
        return self._hash

    def compute_hash(self) -> bytes:
        # Hash(c) := sha256(CellRepr(c))
        return hashlib.sha256(self._cell_repr).digest()

    def order(self, result: dict = {}) -> dict:
        """
        :return: dict {<Cell>: <index>}
        """
        if self in result:
            result.pop(self)
        result[self] = None
        for ref in self.refs:
            ref.order(result)
        return result

    def serialize(self, indexes: dict, byte_len: int) -> bytes:
        result = self._descriptors + self._data_bytes
        for ref in self.refs:
            result += indexes[ref].to_bytes(byte_len, 'big')
        return result

    def to_boc(self, has_idx=False, hash_crc32=False, has_cache_bits=False, flags=0):
        indexed = {}
        self.order(indexed)
        ordered_cells = {j: i for i, j in enumerate(indexed)}  # {root_cell: 0, cell1: 1, cell2: 2 ...}

        cells_num = len(ordered_cells)

        cells_len = (cells_num.bit_length() + 7) // 8  # equals to math.ceil(math.log2(ordered_cells + 1) / 8) but 3x faster

        # flags = 0_0_0_00_000: has_idx 1bit, hash_crc32 1bit, has_cache_bits 1bit, flags 2bit, size_bytes 3 bit
        flags = (has_idx * 128 + hash_crc32 * 64 + has_cache_bits * 32 + flags * 8 + cells_len).to_bytes(1, 'big')

        payload = b''

        serialized_cells_len = []

        for cell in ordered_cells:
            ser_result = cell.serialize(ordered_cells, cells_len)
            payload += ser_result
            serialized_cells_len.append(len(ser_result))

        payload_len = (len(payload).bit_length() + 7) // 8

        root_num = 1  # currently 1
        root_index = b'\00'

        absent = b'\x00'

        result = b'\xb5\xee\x9cr' + \
                 flags + \
                 payload_len.to_bytes(1, 'big') + \
                 cells_num.to_bytes(payload_len, 'big') + \
                 root_num.to_bytes(1, 'big') + \
                 absent + \
                 len(payload).to_bytes(payload_len, 'big') + \
                 root_index

        if has_idx:
            for l in serialized_cells_len:
                result += l.to_bytes(payload_len, 'big')
        result += payload
        if hash_crc32:
            result += crc32c(result)
        return result

    @classmethod
    def one_from_boc(cls, data: typing.Any):
        boc = Boc(data)
        cells = boc.deserialize()
        if len(cells) > 1:
            raise CellError('expected one root cell')
        root_cell = cells[0]
        return root_cell.to_cell()

        # def get_refs(cell: "NullCell"):
        #     refs = []
        #     for ref in cell.refs:
        #         refs.append(cls(ref.bits, get_refs(ref), ref.type_))
        #
        #     return refs
        # return cls(root_cell.bits, get_refs(root_cell), root_cell.type_)

    def to_tonsdk_cell(self, cell_cls):
        return cell_cls.one_from_boc(self.to_boc())

    def __hash__(self) -> int:  # for dicts
        return int.from_bytes(self._hash, 'big')

    def __getitem__(self, ref_i: int) -> "Cell":
        """
        my_cell: Cell
        new_cell = builder().store_ref(my_cell).end_cell()
        assert new_cell[0] == my_cell
        """
        return self.refs[ref_i]

    def __eq__(self, other: "Cell") -> bool:
        return self._hash == other.hash

    def __repr__(self) -> str:
        return f'<Cell {len(self.bits)}[{self.bits.tobytes().hex().upper()}] -> {len(self.refs)} refs>'
