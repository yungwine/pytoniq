import copy
import hashlib
import typing

from bitarray.util import ba2int

from .deserialize import Boc, NullCell
from .exotic import LevelMask, CellTypes
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
    """
    def __init__(self, bits: BitarrayLike, refs: typing.List["Cell"], cell_type: int = -1) -> None:
        self.bits: BitarrayLike = bits
        self.refs: list = refs
        self.type_: int = cell_type
        self.is_exotic: bool = cell_type != -1
        super().__init__(bits, refs, cell_type)

        self.level_mask: LevelMask = self.resolve_mask()
        self._hashes: typing.List[bytes] = []
        self._depths: typing.List[int] = []
        self.calculate_hashes()

        self._descriptors: bytes = self.get_descriptors(self.level_mask)
        self._data_bytes: bytes = self.get_data_bytes()

        self._hash = self._hashes[-1]

    @classmethod
    def empty(cls):
        return cls(TvmBitarray(1023), [], -1)

    def resolve_mask(self) -> LevelMask:
        if self.type_ == CellTypes.ordinary:
            # Ordinary Cell level = max(Cell refs)
            mask = 0
            for r in self.refs:
                mask |= r.level_mask.mask
            return LevelMask(mask)
        elif self.type_ == CellTypes.pruned_branch:
            # prunned branch doesn't have refs
            if self.refs:
                raise CellError('Pruned branch must not has refs')
            return LevelMask(int(self.bits[8:16].to01(), 2))
        elif self.type_ == CellTypes.merkle_proof:
            # merkle proof cell has exactly one ref
            return LevelMask(self.refs[0].level_mask.mask >> 1)
        elif self.type_ == CellTypes.merkle_update:
            # merkle update cell has exactly 2 refs
            return LevelMask((self.refs[0].level_mask.mask | self.refs[1].level_mask.mask) >> 1)
        elif self.type_ == CellTypes.library_ref:
            return LevelMask(0)
        else:
            raise CellError(f'Unknown cell type: {self.type_}')

    def to_builder(self):
        from .builder import Builder
        return Builder().store_cell(self)

    def get_refs_descriptor(self, lvl_mask: LevelMask) -> bytes:
        # d1 = r + 8s + 32l
        d1 = len(self.refs) + 8 * self.is_exotic + 32 * lvl_mask.mask
        return d1.to_bytes(1, 'big')

    def get_bits_descriptor(self) -> bytes:
        # d2 = ceil(b/8) + floor(b/8)
        bit_len = len(self.bits)
        d2 = (bit_len // 8) * 2
        d2 += 1 if bit_len % 8 else 0
        return d2.to_bytes(1, 'big')

    def get_descriptors(self, lvl_mask: LevelMask = LevelMask(0)) -> bytes:
        return self.get_refs_descriptor(lvl_mask) + self.get_bits_descriptor()

    def get_depth(self, lvl_mask: int = 0) -> int:
        hash_index = self.level_mask.apply(lvl_mask).get_hash_index()
        if self.type_ == CellTypes.pruned_branch:
            pruned_hash_index = self.level_mask.get_hash_index()
            if hash_index != pruned_hash_index:
                off = 2 + 32 * pruned_hash_index + hash_index * 2
                return int.from_bytes(self.get_data_bytes()[off: off + 2], 'big')
            hash_index = 0
        return self._depths[hash_index]

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
        # CellRepr(c) = CellRepr∞ (c) = d1d2 + data + depth(r_i) for all i + hash(r_i) for all i
        descs = self._descriptors
        data = self._data_bytes
        result = descs + data
        depths = b''
        hashes = b''
        for ref in self.refs:
            depths += ref._max_depth.to_bytes(2, 'big')
            hashes += ref.hash
        return result + depths + hashes

    @property
    def hash(self) -> bytes:
        return self._hash

    @property
    def data(self) -> bytes:
        return self._data_bytes

    def get_hash(self, lvl_mask) -> bytes:
        # https://github.com/ton-blockchain/ton/blob/master/crypto/vm/cells/DataCell.cpp#L287
        hash_index = self.level_mask.apply(lvl_mask).get_hash_index()
        if self.type_ == CellTypes.pruned_branch:
            pruned_hash_index = self.level_mask.get_hash_index()
            if hash_index != pruned_hash_index:
                # here we read and return hash of the deleted subtree
                return self._data_bytes[2 + (hash_index * 32): 2 + ((hash_index + 1) * 32)]
            hash_index = 0
        return self._hashes[hash_index]

    def calculate_hashes(self) -> None:
        # https://github.com/xssnick/tonutils-go/blob/master/tvm/cell/proof.go#L169
        total_hash_count = self.level_mask.get_hash_index() + 1
        hash_count = total_hash_count
        if self.type_ == CellTypes.pruned_branch:
            hash_count = 1
        hash_index_offset = total_hash_count - hash_count
        hash_index = 0
        level = self.level_mask.get_level()
        for li in range(0, level + 1):
            if not self.level_mask.is_significant(li):
                continue
            if li < hash_index_offset:  # change to range(offset level+1)
                hash_index += 1
                continue
            dsc = self.get_descriptors(self.level_mask.apply(li))
            hash_ = hashlib.sha256(dsc)
            if hash_index == hash_index_offset:
                if li != 0 and self.type_ != CellTypes.pruned_branch:
                    raise CellError('not pruned or 0')
                data = self.get_data_bytes()
                hash_.update(data)
            else:
                if li == 0 or self.type_ == CellTypes.pruned_branch:
                    raise CellError('not pruned or 0')
                off = hash_index - hash_index_offset - 1
                hash_.update(self._hashes[off])
            depth = 0
            for r in self.refs:
                if self.type_ in (CellTypes.merkle_proof, CellTypes.merkle_update):
                    ref_depth = r.get_depth(li + 1)
                else:
                    ref_depth = r.get_depth(li)
                depth_bytes = ref_depth.to_bytes(2, 'big')
                hash_.update(depth_bytes)
                if ref_depth > depth:
                    depth = ref_depth
            if len(self.refs) > 0:
                depth += 1
                if depth >= 1024:  # Cell max depth
                    raise CellError('depth is more than max depth')
            for r in self.refs:
                if self.type_ in (CellTypes.merkle_proof, CellTypes.merkle_update):
                    hash_.update(r.get_hash(li + 1))
                else:
                    hash_.update(r.get_hash(li))
            off = hash_index - hash_index_offset
            self._depths.append(depth)
            self._hashes.append(hash_.digest())
            hash_index += 1

    def calculate_representation_hash(self) -> bytes:
        # Hash_repr(c) := sha256(CellRepr(c))
        return hashlib.sha256(self.get_representation()).digest()

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

        cells_len = (cells_num.bit_length() + 7) // 8  # equals to math.ceil(math.log2(cells_num + 1) / 8) but 3x faster

        # flags = 0_0_0_00_000: has_idx 1bit, hash_crc32 1bit, has_cache_bits 1bit, flags 2bit, size_bytes 3 bit
        flags = (has_idx * 128 + hash_crc32 * 64 + has_cache_bits * 32 + flags * 8 + cells_len)
        flags |= cells_len
        flags = flags.to_bytes(1, 'big')

        payload = b''

        serialized_cells_len = []

        for cell in ordered_cells:
            ser_result = cell.serialize(ordered_cells, cells_len)
            payload += ser_result
            serialized_cells_len.append(len(ser_result))

        payload_len = (len(payload).bit_length() + 7) // 8

        root_num = 1  # currently 1
        root_index = b'\00' * cells_len

        absent = b'\x00' * cells_len

        result = b'\xb5\xee\x9cr' + \
                 flags + \
                 payload_len.to_bytes(1, 'big') + \
                 cells_num.to_bytes(cells_len, 'big') + \
                 root_num.to_bytes(cells_len, 'big') + \
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
    def from_boc(cls, data: typing.Any) -> typing.List["Cell"]:
        boc = Boc(data)
        cells = boc.deserialize(cls)
        return cells

    @classmethod
    def one_from_boc(cls, data: typing.Any) -> "Cell":
        boc = Boc(data)
        cells = boc.deserialize(cls)
        if len(cells) > 1:
            raise CellError('expected one root cell')
        root_cell = cells[0]
        return root_cell

    def begin_parse(self):
        from .slice import Slice
        return Slice(self.bits, self.refs.copy(), self.type_)

    def copy(self):
        #  TODO deepcopy?
        return Cell(self.bits.copy(), copy.deepcopy(self.refs), self.type_)

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
