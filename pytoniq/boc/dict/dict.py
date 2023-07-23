import hashlib
from bitarray import bitarray
import typing

from .. import Slice, CellTypes
from ..address import Address
from ..cell import Cell
from ..builder import Builder
from ..deserialize import NullCell

from .utils import serialize_dict
from .parse import parse_hashmap

Key = typing.Union[int, str, bytes, Address]
Value = typing.Union


class DictError(BaseException):
    pass


class HashMap:

    def __init__(self, key_size: int,
                 value_serializer: typing.Optional[typing.Callable] = None,
                 map_: dict = None,
                 ):

        self.size = key_size
        if map_ is None:
            map_: dict = {}
        self.map = map_
        # self.key_serializer: typing.Callable = key_serializer
        self.value_serializer: typing.Callable = value_serializer

    def set_int_key(self, int_key: int, value):
        if int_key.bit_length() > self.size:
            raise DictError('Key sizes must be the same.')
        self.map[int_key] = value
        return self

    def set(self, key: Key, value, hash_key=False):
        """
        :param key: dict key
        :param value: dict value
        :param hash_key: sha256 hash key. Usually used for tokens onchain metadata.
        :return: self
        Usage examples:
            dict = HashMap(256, value_serializer=lambda src, dest: dest.store_string(src))
            dict.set('name', 'tonpy', hash_key=True).set('description', 'the best lib', hash_key=True)

            dict = HashMap(267).with_coins_values()
            dict.set(key=Address('EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG'), value=15)\
                    .set(key=Address('EQCD39VS5jcptHL8vMjEXrzGaRcCVYto7HUn4bpAOg8xqB2N'), value=10)
        """
        if hash_key:
            key = hashlib.sha256(key.encode()).digest()
        if isinstance(key, bytes):
            key = int.from_bytes(key, 'big', signed=False)
        elif isinstance(key, str):
            key = int.from_bytes(key.encode(), 'big', signed=False)
        elif isinstance(key, Address):
            key = Builder().store_address(key).end_cell().begin_parse().load_uint(267)
        if isinstance(key, int):
            return self.set_int_key(key, value)
        else:
            raise DictError('unknown key type')

    def with_address_values(self):
        self.value_serializer = lambda src, dest: dest.store_address(src)
        return self

    def with_uint_values(self, length: int):
        self.value_serializer = lambda src, dest: dest.store_uint(src, length)
        return self

    def with_int_values(self, length: int):
        self.value_serializer = lambda src, dest: dest.store_int(src, length)
        return self

    def with_coins_values(self):
        self.value_serializer = lambda src, dest: dest.store_coins(src)
        return self

    def serialize(self) -> typing.Optional[Cell]:
        if not self.value_serializer:
            self.value_serializer = lambda src, dest: dest.store_cell(src)
        if len(self.map):
            return serialize_dict(self.map, self.size, self.value_serializer).end_cell()
        else:
            return None

    @classmethod
    def from_cell(cls, dict_cell: Cell, key_length: int) -> "HashMap":
        dict_result = parse_hashmap(dict_cell.begin_parse(), key_length)
        map_ = {int(i, 2): j for i, j in dict_result.items()}
        result = cls(key_length)
        result.map = map_
        return result

    @staticmethod
    def parse(dict_cell: Slice,  # NullCell or any inherited class with dict
              key_length: int,  # bits len of key
              key_deserializer: typing.Callable = None,  # func to deserialize keys
              value_deserializer: typing.Callable = None  # func to deserialize values
              ) -> typing.Optional[dict]:

        if dict_cell.type_ != CellTypes.ordinary:
            return None

        if not key_deserializer:
            key_deserializer = lambda i: int(i, 2)  # by default key_deserializer just converts bitstring to int
        dict_result = parse_hashmap(dict_cell, key_length)
        if value_deserializer:
            result = {key_deserializer(i): value_deserializer(j.to_slice()) for i, j in dict_result.items()}
        else:
            result = {key_deserializer(i): j for i, j in
                      dict_result.items()}  # if you do not provide value_deserializer the values are NullCells
        return result

    #
    # @classmethod
    # def with_address_keys(cls):
    #     return cls(267,
    #                key_serializer=lambda src: Builder().store_address(src).end_cell().begin_parse().load_bits(267),
    #                value_serializer=None)
    #
    # def with_address_values(self):
    #     self.value_serializer = lambda src, dest: dest.store_address(src)
    #     return self
    #
    # @classmethod
    # def with_uint_keys(cls, bit_length: int):
    #     return cls(
    #         bit_length,
    #         key_serializer=lambda k: Builder().store_uint(k).end_cell().begin_parse().load_bits(267),
    #
    #     )
