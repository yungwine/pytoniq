from typing import Union, Iterable, overload

from bitarray import bitarray
from bitarray.util import int2ba


BytesLike = Union[bytes, Iterable[int]]


class TvmBitarrayException(BaseException):
    pass


class TvmBitarrayOverflowException(TvmBitarrayException):
    pass


class TvmBitarray(bitarray):

    def __new__(cls, size: int = 1023, *args, **kwargs):
        return super().__new__(cls, *args, **kwargs)

    def __init__(self, size: int = 1023, *args, **kwargs):
        if size > 1023:
            raise TvmBitarrayException('bitarray size must be <= 1023')
        self._size = size
        super().__init__()

    def check_overflow(self, length: int) -> None:
        if len(self) + length > 1023:
            raise TvmBitarrayOverflowException('bitstring overflow')

    def check_underflow(self, length: int) -> None:
        if len(self) < length:
            raise TvmBitarrayOverflowException('bitstring underflow')

    def extend(self, x: Union[str, Iterable[int]]) -> None:
        self.check_overflow(len(x))
        super().extend(x)

    def append(self, value: int) -> None:
        self.check_overflow(1)
        super().append(value)

    def frombytes(self, a: BytesLike) -> None:
        self.check_overflow(len(a) * 8)
        super().frombytes(a)

    def copy(self) -> "TvmBitarray":
        res = self.__new__(TvmBitarray)
        res.extend(self)
        return res

    def __delitem__(self, item: Union[int, slice]):
        if isinstance(item, slice):
            start = item.start if item.start else 0
            stop = item.stop if item.stop else len(self)
            self.check_underflow(stop - start)
        elif isinstance(item, int):
            self.check_underflow(1)
        return super().__delitem__(item)

    def to_bitarray(self):
        return bitarray(self)


BitarrayLike = Union[TvmBitarray, bitarray]
