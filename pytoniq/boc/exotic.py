"""
This is quite an advanced level, so it is highly recommended that you first become familiar with https://docs.ton.org/tvm.pdf 3.1.2 - 3.1.7
"""


class CellTypes:
    ordinary = -1
    pruned_branch = 1
    library_ref = 2
    merkle_proof = 3
    merkle_update = 4


class LevelMask:
    # https://github.com/xssnick/tonutils-go/blob/master/tvm/cell/level.go#L17
    def __init__(self, m: int):
        self._m = m
        self._level = self.get_level()
        self._hash_index = self.get_hash_index()

    @property
    def mask(self):
        return self._m

    @property
    def level(self):
        return self._level

    @property
    def hash_index(self):
        return self._hash_index

    def get_level(self):
        return self._m.bit_length()

    def get_hash_index(self):
        return self._m.bit_count()

    def apply(self, level: int):
        return LevelMask(self._m & ((1 << level) - 1))

    def is_significant(self, level: int):
        return level == 0 or (self._m >> (level - 1)) % 2 != 0

