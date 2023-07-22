import copy
import math
import timeit

# from bitarray import bitarray
from bitarray.util import int2ba

import typing

from .address import Address
from .cell import Cell
from .deserialize import NullCell
from .tvm_bitarray import TvmBitarray


class Builder(NullCell):

    def __init__(self, size: int = 1023, type_: int = -1):
        self._size = size
        self._bits = TvmBitarray(size)
        self._refs = []
        self._type = type_

    @property
    def bits(self):
        return self._bits

    @property
    def refs(self):
        return self._refs

    @property
    def size(self):
        return self._size

    @size.setter
    def size(self, new_size: int):
        assert new_size <= 1023, 'builder size cannot be more than 1023 bits'

    @bits.setter
    def bits(self, new_bits: TvmBitarray):
        self._bits = new_bits

    @refs.setter
    def refs(self, new_refs: typing.List[Cell]):
        self._refs = new_refs

    def to_bytes(self):
        return self._bits.tobytes()

    def store_cell(self, cell: Cell):
        self.store_bits(cell.bits)
        self._refs += cell.refs
        return self

    def store_slice(self, cell_slice: "Slice"):
        self.store_bits(cell_slice.bits)
        for i in range(cell_slice.ref_offset, len(cell_slice.refs)):
            self.store_ref(cell_slice.refs[i])
        return self

    def store_ref(self, ref: Cell):
        assert len(self._refs) <= 4, 'builder refs overflow'
        self._refs.append(copy.deepcopy(ref))
        return self

    def store_bool(self, value: bool):
        self.bits.append(value)
        return self

    def store_bit_int(self, bit: int):
        self.bits.append(bit)
        return self

    def store_bit(self, bit: typing.Union[int, bool, str, TvmBitarray]):
        if isinstance(bit, (int, bool)):
            self.bits.append(bit)
        elif isinstance(bit, str):
            self.bits.append(int(bit))
        elif isinstance(bit, TvmBitarray):
            self.bits.extend(bit[:1])
        return self

    def store_bits(self, bits: typing.Union[str, typing.Iterable[int], TvmBitarray]):
        self.bits.extend(bits)
        return self

    def store_maybe_ref(self, ref: typing.Optional[Cell]):
        if ref is None:
            self.store_bit(0)
        else:
            self.store_bit(1)
            self.store_ref(ref)
        return self

    def store_uint(self, value: int, size: int):
        self._bits.extend(int2ba(value, size, signed=False))
        return self

    def store_int(self, value: int, size: int):
        self._bits.extend(int2ba(value, size, signed=True))
        return self

    def store_var_uint(self, value: int, bit_length: int):
        if value == 0:
            self.store_uint(0, bit_length)
            return self
        byte_length = math.ceil(value.bit_length() / 8)
        return self.store_uint(byte_length, bit_length).store_uint(value, byte_length * 8)

    def store_var_int(self, value: int, bit_length: int):
        if value == 0:
            self.store_uint(0, bit_length)
        byte_length = math.ceil(value.bit_length() / 8)
        return self.store_uint(byte_length, bit_length).store_int(value, byte_length * 8)

    def store_coins(self, amount: int):
        return self.store_var_uint(amount, 4)

    def store_bytes(self, value: typing.Union[bytes, bytearray]):
        self._bits.frombytes(value)
        return self

    def store_string(self, value: str):
        self._bits.frombytes(value.encode())
        return self

    def store_address(self, address):
        if address is None:
            self.store_bits('00')
            return self
        if isinstance(address, str):
            address = Address(address)

        self.store_bits('100')  # addr_std$10 + maybe anycast = 0

        return self.store_int(address.wc, 8).store_bytes(address.hash_part)

    def store_dict(self, dict_: typing.Optional[Cell] = None):
        return self.store_maybe_ref(dict_)

    def end_cell(self) -> Cell:
        return Cell(self._bits, self._refs, self._type)

    def __repr__(self) -> str:
        return f'<Builder {len(self.bits)}[{self.bits.tobytes().hex().upper()}] -> {len(self.refs)} refs>'
