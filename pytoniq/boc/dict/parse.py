import typing

from .. import Slice, CellTypes
from ..deserialize import NullCell

from bitarray import bitarray


def read_arbitrary_uint(n: int, ser: bitarray) -> typing.Tuple[int, bitarray]:
    x = 0
    for i in range(n):
        x <<= 1
        r = ser.pop(0)
        x += r
    return x, ser


def deserialize_unary(ser: Slice) -> int:
    n = 0
    r = ser.load_bit()
    while r:
        n += 1
        r = ser.load_bit()
    return n


def deserialize_hml(ser: Slice, m: int) -> typing.Tuple[int, bitarray]:
    _type = ''
    k = ser.load_bit()
    if k:
        k = ser.load_bit()
        if k:  # 11
            _type = 'same'
        else:  # 10
            _type = 'long'
    else:  # 0
        _type = 'short'
    if _type == 'short':
        n = deserialize_unary(ser)
        s = ser.load_bits(n)
    elif _type == 'long':
        l = m.bit_length()
        n = ser.load_uint(l)
        s = ser.load_bits(n)
    else:  # same
        v = ser.load_bit()
        l = m.bit_length()
        n = ser.load_uint(l)
        s = bitarray(str(v) * n)
    return n, s


def deserialize_hashmap_node(cs: Slice, m: int, ret_dict: dict, prefix: bitarray) -> None:
    if cs.type_ != CellTypes.ordinary:
        return None
    if m == 0:  # leaf
        if prefix:
            ret_dict[prefix.to01()] = cs
    else:  # fork
        l_prefix, r_prefix = prefix.copy(), prefix.copy()
        l_prefix.append(False)
        r_prefix.append(True)
        parse(
            cs.load_ref().begin_parse(),
            m - 1,
            ret_dict,
            l_prefix,
            )
        parse(
            cs.load_ref().begin_parse(),
            m - 1,
            ret_dict,
            r_prefix,
            )


def deserialize_hashmap_aug_node(cs: Slice, m: int, ret_dict: dict, extras: list, prefix: bitarray, x_deserializer: typing.Callable, y_deserializer: typing.Callable) -> None:
    if m == 0:  # ahmn_leaf
        extras.append(y_deserializer(cs))
        ret_dict[prefix.to01()] = x_deserializer(cs)
    else:  # ahmn_fork
        l_prefix, r_prefix = prefix.copy(), prefix.copy()
        l_prefix.append(False)
        r_prefix.append(True)
        parse_aug(
            cs.load_ref().begin_parse(),
            m - 1,
            ret_dict,
            extras,
            l_prefix,
            x_deserializer,
            y_deserializer
            )
        parse_aug(
            cs.load_ref().begin_parse(),
            m - 1,
            ret_dict,
            extras,
            r_prefix,
            x_deserializer,
            y_deserializer
            )
        extras.append(y_deserializer(cs))


def parse(slice: Slice, key_length: int, ret_dict: dict, prefix: bitarray) -> None:
    l, suffix = deserialize_hml(slice, key_length)
    prefix.extend(suffix)
    m = key_length - l
    deserialize_hashmap_node(slice, m, ret_dict, prefix.copy())


def parse_aug(slice: Slice, key_length: int, ret_dict: dict, extras: list, prefix: bitarray, x_deserializer: typing.Callable, y_deserializer: typing.Callable) -> None:
    if slice.type_ != CellTypes.ordinary:
        return None
    l, suffix = deserialize_hml(slice, key_length)
    prefix.extend(suffix)
    m = key_length - l
    deserialize_hashmap_aug_node(slice, m, ret_dict, extras, prefix.copy(), x_deserializer, y_deserializer)


def parse_hashmap(dict_cell: Slice, key_len: int) -> typing.Optional[dict]:
    result = {}
    parse(dict_cell, key_len, result, bitarray(''))
    return result


def parse_hashmap_aug(dict_cell: Slice, key_len: int, x_deserializer: typing.Callable, y_deserializer: typing.Callable) -> typing.Optional[typing.Tuple[dict, list]]:
    if dict_cell.type_ != CellTypes.ordinary:
        return None
    result = {}
    extras = []
    parse_aug(dict_cell, key_len, result, extras, bitarray(''), x_deserializer, y_deserializer)
    result = {int(i, 2): j for i, j in result.items()}
    return result, extras
