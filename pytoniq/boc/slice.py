import typing
from copy import deepcopy
from bitarray.util import ba2int

from .deserialize import Boc, NullCell
from .cell import Cell
from .tvm_bitarray import bitarray, TvmBitarray, BitarrayLike
from .address import Address


class Slice(NullCell):

    def __init__(self, bits: TvmBitarray, refs: typing.List[Cell], type_: int = -1):
        self.bits = bits.copy()
        self.refs = refs
        self.type_ = type_
        # super().__init__(bits, refs, type_)
        self.ref_offset = 0

    def is_special(self):
        from . import CellTypes
        return False if self.type_ == CellTypes.ordinary else True

    def preload_bit(self) -> int:
        return self.bits[0]

    def load_bit(self) -> int:
        bit = self.preload_bit()
        del self.bits[0]
        return bit

    def preload_bool(self) -> bool:
        return bool(self.bits[0])

    def load_bool(self) -> bool:
        bit = self.preload_bit()
        del self.bits[0]
        return bool(bit)

    def skip_bits(self, length: int) -> "Slice":
        del self.bits[:length]
        return self

    def preload_bits(self, length: int) -> BitarrayLike:
        bits = self.bits[:length]
        return bits

    def load_bits(self, length: int) -> BitarrayLike:
        bits = self.preload_bits(length)
        del self.bits[:length]
        return bits

    def preload_uint(self, length: int) -> int:
        return ba2int(self.bits[:length], signed=False)

    def load_uint(self, length: int) -> int:
        uint = self.preload_uint(length)
        del self.bits[:length]
        return uint

    def preload_int(self, length: int) -> int:
        return ba2int(self.bits[:length], signed=True)

    def load_int(self, length: int) -> int:
        integer = self.preload_int(length)
        del self.bits[:length]
        return integer

    def preload_bytes(self, length: int) -> bytes:
        return self.bits[:length * 8].tobytes()

    def load_bytes(self, length: int) -> bytes:
        bytes_ = self.preload_bytes(length)
        del self.bits[:length * 8]
        return bytes_

    def preload_address(self) -> typing.Optional[Address]:
        # address := flags 2bits, anycast 1bit, workchain 8bits, hash_part 256bits = 267 bits
        if self.preload_uint(2) == 0:
            return None
        rem = self.preload_bits(265)  # 267 - 2

        wc = ba2int(rem[1:9], signed=True)
        hash_part = rem[9:].tobytes()

        return Address((wc, hash_part))

    def load_address(self) -> typing.Optional[Address]:
        # address := flags 2bits, anycast 1bit, workchain 8bits, hash_part 256bits = 267 bits
        if self.load_uint(2) == 0:
            return None
        self.skip_bits(1)
        wc = self.load_int(8)
        hash_part = self.load_bytes(32)
        return Address((wc, hash_part))

    def preload_var_uint(self, bit_length: int) -> int:
        length = self.preload_uint(bit_length)
        if not length:
            return 0
        coins = self.preload_bits(bit_length + length * 8)[bit_length:]
        return ba2int(coins, signed=False)

    def load_var_uint(self, bit_length: int) -> typing.Optional[int]:
        length = self.load_uint(bit_length)
        if not length:
            return None
        return self.load_uint(length * 8)

    def preload_coins(self) -> int:
        length = self.preload_uint(4)
        if not length:
            return 0
        coins = self.preload_bits(4 + length * 8)[4:]
        return ba2int(coins, signed=False)

    def load_coins(self) -> typing.Optional[int]:
        length = self.load_uint(4)
        if not length:
            return 0
        return self.load_uint(length * 8)

    def preload_string(self, byte_length: int = 0):
        if byte_length == 0:
            byte_length = len(self.bits) // 8
        return self.preload_bytes(byte_length)

    def load_string(self, byte_length: int = 0):
        if byte_length == 0:
            byte_length = len(self.bits) // 8
        return self.load_bytes(byte_length)

    def preload_ref(self) -> Cell:
        return self.refs[self.ref_offset]

    def load_ref(self) -> Cell:
        ref = self.refs[self.ref_offset]
        self.ref_offset += 1
        return ref

    def preload_maybe_ref(self) -> typing.Optional[Cell]:
        if self.preload_bool():
            return self.refs[self.ref_offset]
        else:
            return None

    def load_maybe_ref(self) -> typing.Optional[Cell]:
        if self.load_bit():
            ref = self.refs[self.ref_offset]
            self.ref_offset += 1
            return ref
        else:
            return None

    def load_hashmap(self, key_length: int, key_deserializer: typing.Callable = None,
                     value_deserializer: typing.Callable = None):
        from .dict.dict import HashMap
        return HashMap.parse(self, key_length, key_deserializer, value_deserializer)

    def load_hashmap_aug(self, key_length: int, x_deserializer: typing.Callable = None,
                         y_deserializer: typing.Callable = None):
        from .dict.parse import parse_hashmap_aug
        return parse_hashmap_aug(self, key_length, x_deserializer, y_deserializer)

    def load_hashmap_aug_e(self, key_length: int, x_deserializer: typing.Callable = None,
                           y_deserializer: typing.Callable = None):
        if self.is_special():
            return self.to_cell()
        if self.load_bit():
            from .dict.parse import parse_hashmap_aug
            return parse_hashmap_aug(self.load_ref().begin_parse(), key_length, x_deserializer, y_deserializer)
        else:
            return {}, [self]  # extra

    def preload_dict(self, key_length: int, key_deserializer: typing.Callable = None,
                     value_deserializer: typing.Callable = None):
        from .dict.dict import HashMap
        if self.preload_bit():
            return HashMap.parse(self.preload_ref().begin_parse(), key_length, key_deserializer, value_deserializer)
        else:
            return None

    def load_dict(self, key_length: int, key_deserializer: typing.Callable = None,
                  value_deserializer: typing.Callable = None):
        from .dict.dict import HashMap
        if self.load_bit():
            return HashMap.parse(self.load_ref().begin_parse(), key_length, key_deserializer, value_deserializer)
        else:
            return None

    @classmethod
    def from_cell(cls, cell: "Cell"):
        return cls(cell.bits, cell.refs, cell.type_)

    @classmethod
    def one_from_boc(cls, data: typing.Any) -> "Slice":
        boc = Boc(data)
        cells = boc.deserialize()
        return cells[0].begin_parse()

    def copy(self):
        return Slice(self.bits.copy(), deepcopy(self.refs), self.type_)

    def __repr__(self) -> str:
        return f'<Slice {len(self.bits)}[{self.bits.tobytes().hex().upper()}] -> {len(self.refs) - self.ref_offset} refs>'

    def __str__(self, t=1, comma=False) -> str:
        """
        :param t: \t symbols amount before text
        :param comma: "," after "}"
        """
        text = f'{len(self.bits)}[{self.bits.tobytes().hex().upper()}]'
        if self.refs:
            text += f' -> {{\n'
            for index, ref in enumerate(self.refs[self.ref_offset:]):
                next_comma = True if index != len(self.refs) - 1 else False
                text += '\t' * t + ref.__str__(t + 1, next_comma) + '\n'
            text += '\t' * (t - 1) + '}'
        if comma:
            text += ','
        return text
