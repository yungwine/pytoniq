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

    def __init__(self, size: int = 1023):
        self._size = size
        self._bits = TvmBitarray(size)
        self._refs = []

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

    def store_ref(self, ref: Cell):
        assert len(self._refs) < 5, 'builder refs overflow'
        self._refs.append(ref)
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

        self.store_bits('100')  # address is not None = 10 + anycast = 0

        return self.store_int(address.wc, 8).store_bytes(address.hash_part)

    def store_coins(self, amount: int):
        byte_length = math.ceil(amount.bit_length() / 8)
        return self.store_uint(byte_length, 4).store_uint(amount, 32)

    def store_dict(self): ...

    def end_cell(self) -> Cell:
        return Cell(self._bits, self._refs)
