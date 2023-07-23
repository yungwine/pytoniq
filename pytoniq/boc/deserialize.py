import base64
import binascii
import copy
import typing

from bitarray.util import ba2int

from .tvm_bitarray import bitarray, TvmBitarray
from .utils import bytes_to_uint
from ..crypto.crc import crc32c


class BocError(BaseException):
    pass


# https://github.com/ton-blockchain/ton/blob/24dc184a2ea67f9c47042b4104bbb4d82289fac1/crypto/tl/boc.tlb#L25
SERIALIZED_BOC_IDX_CRC32C = b'\xac\xc3\xa7('  # LEAN_BOC_MAGIC_PREFIX_CRC acc3a728
SERIALIZED_BOC_IDX_PREFIX = b'h\xffe\xf3'  # LEAN_BOC_MAGIC_PREFIX 68ff65f3
SERIALIZED_BOC_PREFIX = b'\xb5\xee\x9cr'  # REACH_BOC_MAGIC_PREFIX b5ee9c72


class NullCell:
    """
    NullCell is a class that stores cell bits, and refs to other NullCells.
    This class needed to deserialize boc (bag of cells) and convert it into Cell, Builder or Slice
    """
    def __init__(self, bits: TvmBitarray, refs: list, type_: int):
        self.bits = bits
        self.refs = refs
        self.type_ = type_

    def get_refs(self, cls: type):
        refs = []
        for ref in self.refs:
            refs.append(cls(ref.bits, ref.get_refs(cls), ref.type_))

        return refs

    def to_cell(self):
        from .cell import Cell
        return Cell(self.bits, self.get_refs(Cell), self.type_)

    def to_slice(self):
        from .slice import Slice
        from .cell import Cell
        return Slice(self.bits, self.get_refs(Cell), )

    def to_builder(self):
        from .builder import Builder
        cell = self.to_cell()
        return Builder().store_cell(cell)

    def copy(self):
        return NullCell(self.bits.copy(), copy.deepcopy(self.refs.copy()), self.type_)

    def __repr__(self) -> str:
        return f'<NullCell {len(self.bits)}[{self.bits.tobytes().hex().upper()}] -> {len(self.refs)} refs>'

    def __str__(self, t=1, comma=False) -> str:
        """
        :param t: \t symbols amount before text
        :param comma: "," after "}"
        """
        text = f'{len(self.bits)}[{self.bits.tobytes().hex().upper()}]'
        if self.refs:
            text += f' -> {{\n'
            for index, ref in enumerate(self.refs):
                next_comma = True if index != len(self.refs) - 1 else False
                text += '\t' * t + ref.__str__(t + 1, next_comma) + '\n'
            text += '\t' * (t - 1) + '}'
        if comma:
            text += ','
        return text


class Boc:

    def __init__(self, data: typing.Union[bytes, str]):
        if not isinstance(data, bytes):
            try:
                data = bytes.fromhex(data)
            except ValueError:
                try:
                    data = base64.b64decode(data)
                except binascii.Error:
                    raise BocError('boc data in unknown form')
        self.data = data
        self.data_len = len(data)

    @classmethod
    def from_base64(cls, data: str):
        return cls(base64.b64decode(data))

    @classmethod
    def from_hex(cls, data: str):
        return cls(bytes.fromhex(data))

    def parse(self):
        pass

    @staticmethod
    def deserialize_boc_header(data: bytes):
        # TODO: check if this implementation is really faster than bytes slicing
        data_len = len(data)
        if data_len < 4:
            raise BocError(f'not enough bytes to deserialize boc header: {data}')
        result = {
            'has_idx': True,
            'hash_crc32': None,
            'has_cache_bits': False,
            'flags': 0,
            'size_bytes': data[0],
            'offset_bytes': None,
            'cells_num': None,
            'roots_num': None,
            'absent_num': None,
            'tot_cells_size': None,
            'root_list': None,
            'index': None,
            'cells_data': None,
        }
        if data[:4] == SERIALIZED_BOC_PREFIX:
            flags_byte = data[4]
            result['has_idx'] = flags_byte & 128
            result['hash_crc32'] = flags_byte & 64
            result['has_cache_bits'] = flags_byte & 32
            result['flags'] = (flags_byte & 16) * 2 + (flags_byte & 8)
            result['size_bytes'] = flags_byte % 8
        elif data[:4] == SERIALIZED_BOC_IDX_PREFIX:
            result['hash_crc32'] = 0
        elif data[:4] == SERIALIZED_BOC_IDX_CRC32C:
            result['hash_crc32'] = 1
        else:
            raise BocError(f'unknown boc prefix: {data[:4]}')
        if data_len - 5 < 1 + 5 * result['size_bytes']:
            raise BocError(f'can\'t parse boc header: {data[:4]}')
        offset_bytes = data[5]
        result['offset_bytes'] = offset_bytes
        size_bytes = result['size_bytes']

        end = 6 + 3 * size_bytes
        result['cells_num'], result['roots_num'], result['absent_num'] \
            = [bytes_to_uint(data[i: i + size_bytes]) for i in range(6, end, size_bytes)]

        i = end + result['offset_bytes']
        result['tot_cells_size'] = bytes_to_uint(data[end: i])

        if data_len - i < result['roots_num'] * size_bytes:
            raise Exception("Not enough bytes for encoding root cells hashes")
        end = i + result['roots_num'] * size_bytes
        result['root_list'] = [bytes_to_uint(data[j: j + size_bytes]) for j in range(i, end,  size_bytes)]
        i = end
        if result['has_idx']:
            if data_len - i < offset_bytes * result['cells_num']:
                raise BocError("Not enough bytes for index encoding")
            end = i + result['cells_num'] * offset_bytes
            result['index'] = [bytes_to_uint(data[j: j + offset_bytes]) for j in range(i, end,  offset_bytes)]
            i = end

        if data_len - i < result['tot_cells_size']:
            raise BocError("Not enough bytes for cells data")

        end = i + result['tot_cells_size']
        result['cells_data'] = data[i: end]
        i = end

        if result['hash_crc32']:
            if data_len - i < 4:
                raise BocError("Not enough bytes for crc32c hashsum")
            if crc32c(data[: i]) != data[i: i + 4]:
                raise BocError("Crc32c hashsum mismatch")
            i += 4
        if data_len - i:  # != 0
            raise BocError("Too many bytes in boc")
        return result

    @staticmethod
    def deserialize_cell(data: bytes, ref_index_size: int) -> typing.Tuple[dict, int]:
        data_len = len(data)
        refs_descriptor = data[0]
        level = refs_descriptor >> 5
        total_refs = refs_descriptor & 7
        has_hashes = (refs_descriptor & 16) != 0
        is_exotic = refs_descriptor & 8
        is_absent = total_refs == 7 and has_hashes
        if is_absent:
            raise BocError('can\'t deserialize absent cell')
        bits_descriptor = data[1]
        is_augmented = bits_descriptor & 1
        data_size = (bits_descriptor >> 1) + is_augmented
        hashes_size = (level + 1) * 32 if has_hashes else 0
        depth_size = (level + 1) * 2 if hashes_size else 0
        i = 2

        if data_len - i < hashes_size + depth_size + data_size + ref_index_size * total_refs:
            raise BocError('Not enough bytes to encode cell data')

        if has_hashes:
            i += hashes_size + depth_size
        bits = bitarray()
        bits.frombytes(data[i: i + data_size])
        i += data_size

        end = None
        if is_augmented and bits:
            for j in range(-1, -8, -1):
                if bits[j] == 1:
                    end = j
                    break
        bits = TvmBitarray(1023, bits[:end])

        if is_exotic:
            if len(bits) < 8:
                raise BocError('not enough bytes for an exotic cell type')
            cell_type = ba2int(bits[:8], signed=True)
        else:
            cell_type = -1

        cell_refs_indexes = []
        for r in range(total_refs):
            cell_refs_indexes.append(bytes_to_uint(data[i: i + ref_index_size]))
            i += ref_index_size

        # cell = NullCell(bits, cell_refs_indexes, cell_type)
        cell = {'bits': bits, 'refs': cell_refs_indexes, 'type': cell_type, 'result': None}

        return cell, i

    def deserialize(self, cls: type = None):
        if not cls:
            from .cell import Cell
            cls = Cell

        header = self.deserialize_boc_header(self.data)
        cells_data = header['cells_data']
        cells_array = []

        i = 0

        for ci in range(header['cells_num']):
            cell, j = self.deserialize_cell(cells_data[i:], header['size_bytes'])
            i += j
            cells_array.append(cell)

        for ci in reversed(range(header['cells_num'])):
            c = cells_array[ci]
            refs = []
            for ri in range(len(c['refs'])):
                r = c['refs'][ri]
                if r < ci:
                    raise Exception('Topological order is broken')
                refs.append(cells_array[r]['result'])
            cells_array[ci]['result'] = cls(cells_array[ci]['bits'], refs, cells_array[ci]['type'])

        root_cells = []
        for ri in header['root_list']:
            root_cells.append(cells_array[ri]['result'])

        return root_cells
