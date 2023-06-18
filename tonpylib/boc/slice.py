import typing
from bitarray.util import ba2int

from .deserialize import Boc
from .tvm_bitarray import bitarray, TvmBitarray, BitarrayLike
from .address import Address


class Slice:

    def __init__(self, bits: TvmBitarray, refs: typing.List["NullCell"]):
        self._bits = bits
        self.refs = refs
        self.ref_offset = 0

    def preload_bit(self) -> int:
        return self._bits[0]

    def load_bit(self) -> int:
        bit = self.preload_bit()
        del self._bits[0]
        return bit

    def skip_bits(self, length: int) -> "Slice":
        del self._bits[:length]
        return self

    def preload_bits(self, length: int) -> BitarrayLike:
        bits = self._bits[:length]
        return bits

    def load_bits(self, length: int) -> BitarrayLike:
        bits = self.preload_bits(length)
        del self._bits[:length]
        return bits

    def preload_uint(self, length: int) -> int:
        return ba2int(self._bits[:length], signed=False)

    def load_uint(self, length: int) -> int:
        uint = self.preload_uint(length)
        del self._bits[:length]
        return uint

    def preload_int(self, length: int) -> int:
        return ba2int(self._bits[:length], signed=True)

    def load_int(self, length: int) -> int:
        integer = self.preload_int(length)
        del self._bits[:length]
        return integer

    def preload_bytes(self, length: int) -> bytes:
        return self._bits[:length * 8].tobytes()

    def load_bytes(self, length: int) -> bytes:
        bytes_ = self.preload_bytes(length)
        del self._bits[:length * 8]
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

    def preload_coins(self) -> int:
        length = self.preload_uint(4)
        if not length:
            return 0
        coins = self.preload_bits(4 + length * 8)[4:]
        return ba2int(coins, signed=False)

    def load_coins(self) -> typing.Optional[int]:
        length = self.load_uint(4)
        if not length:
            return None
        return self.load_uint(length * 8)

    def preload_ref(self):
        return self.refs[self.ref_offset]

    def load_ref(self):
        ref = self.refs[self.ref_offset]
        self.ref_offset += 1
        return ref

    def load_dict(self): ...

    @staticmethod
    def one_from_boc(data: typing.Any):
        boc = Boc(data)
        cells = boc.deserialize()
        return cells[0].to_slice()

    def __repr__(self) -> str:
        return f'<Slice {len(self._bits)}[{self._bits.tobytes().hex().upper()}] -> {len(self.refs)} refs>'

    def __str__(self, t=1, comma=False) -> str:
        """
        :param t: \t symbols amount before text
        :param comma: "," after "}"
        """
        text = f'{len(self._bits)}[{self._bits.tobytes().hex().upper()}]'
        if self.refs:
            text += f' -> {{\n'
            for index, ref in enumerate(self.refs):
                next_comma = True if index != len(self.refs) - 1 else False
                text += '\t' * t + ref.__str__(t + 1, next_comma) + '\n'
            text += '\t' * (t - 1) + '}'
        if comma:
            text += ','
        return text
