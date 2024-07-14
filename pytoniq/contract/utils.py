import time

def generate_query_id(offset: int = 7200):
    return int(time.time() + offset) << 32

BIT_NUMBER_SIZE = 10  # 10 bit
SHIFT_SIZE = 13  # 13 bit
MAX_BIT_NUMBER = 1022
MAX_SHIFT = 8191  # 2^13 = 8192

class HighloadQueryId:
    def __init__(self) -> None:
        self._shift = 0
        self._bit_number = 0

    @staticmethod
    def from_shift_and_bit_number(
        shift: int, bit_number: int
    ) -> "HighloadQueryId":
        
        if not (0 <= shift <= MAX_SHIFT):
            raise ValueError("invalid shift")
        if not (0 <= bit_number <= MAX_BIT_NUMBER):
            raise ValueError("invalid bitnumber")

        q = HighloadQueryId()
        q._shift = shift
        q._bit_number = bit_number
        return q

    def get_next(self) -> "HighloadQueryId":
        new_bit_number = self._bit_number + 1
        new_shift = self._shift

        if new_shift == MAX_SHIFT and new_bit_number > (MAX_BIT_NUMBER - 1):
            # we left one queryId for emergency withdraw
            raise ValueError("Overload")

        if new_bit_number > MAX_BIT_NUMBER:
            new_bit_number = 0
            new_shift += 1
            if new_shift > MAX_SHIFT:
                raise ValueError("Overload")

        return HighloadQueryId.from_shift_and_bit_number(
            new_shift, new_bit_number
        )

    def has_next(self) -> bool:
        is_end = (
            self._bit_number >= (MAX_BIT_NUMBER - 1)
            and self._shift == MAX_SHIFT
        )
        return not is_end

    @property
    def shift(self) -> int:
        return self._shift

    @property
    def bit_number(self) -> int:
        return self._bit_number

    @property
    def query_id(self) -> int:
        return (self._shift << BIT_NUMBER_SIZE) + self._bit_number

    @staticmethod
    def from_query_id(query_id: int) -> "HighloadQueryId":
        shift = query_id >> BIT_NUMBER_SIZE
        bit_number = query_id & 1023
        return HighloadQueryId.from_shift_and_bit_number(shift, bit_number)

    @staticmethod
    def from_seqno(i: int) -> "HighloadQueryId":
        shift = i // 1023
        bit_number = i % 1023
        return HighloadQueryId.from_shift_and_bit_number(shift, bit_number)

    def to_seqno(self) -> int:
        return self._bit_number + self._shift * 1023