import typing

from ..deserialize import NullCell

from bitarray import bitarray


def read_arbitrary_uint(n: int, ser: bitarray) -> typing.Tuple[int, bitarray]:
    x = 0
    for i in range(n):
        x <<= 1
        r = ser.pop(0)
        x += r
    return x, ser


def deserialize_unary(ser: bitarray) -> typing.Tuple[int, bitarray]:
    n = 0
    while True:
        r = ser.pop(0)
        if r:
            n += 1
        else:
            return n, ser


def deserialize_hml(ser: bitarray, m: int) -> typing.Tuple[int, bitarray, bitarray]:
    _type = ''
    k = ser.pop(0)
    if k:
        k = ser.pop(0)
        if k:
            _type = 'same'
        else:
            _type = 'long'
    else:
        _type = 'short'
    if _type == 'short':
        _len, ser = deserialize_unary(ser)
        s, ser = ser[:_len], ser[_len:]
    elif _type == 'long':
        _len, ser = read_arbitrary_uint(m.bit_length(), ser)
        s, ser = ser[:_len], ser[_len:]
    else:
        v, ser = ser[0:1], ser[1:]
        _len, ser = read_arbitrary_uint(m.bit_length(), ser)
        s = v * _len
    return _len, s, ser


def deserialize_hashmap_node(cell: NullCell, m: int, ret_dict: dict, prefix: bitarray) -> None:
    if m == 0:  # leaf
        ret_dict[prefix.to01()] = cell
    else:  # fork
        l_prefix, r_prefix = prefix.copy(), prefix.copy()
        l_prefix.append(False)
        r_prefix.append(True)
        parse(
            cell.refs[0].copy(),
            m - 1,
            ret_dict,
            l_prefix,
            )
        parse(
            cell.refs[1].copy(),
            m - 1,
            ret_dict,
            r_prefix,
            )


def parse(cell: NullCell, bit_length: int, ret_dict: dict, prefix: bitarray) -> None:
    _len, suffix, cell.bits = deserialize_hml(cell.bits, bit_length)
    prefix.extend(suffix)
    m = bit_length - _len
    deserialize_hashmap_node(cell.copy(), m, ret_dict, prefix.copy())


def parse_hashmap(dict_cell: NullCell, key_len: int) -> dict:
    result = {}
    parse(dict_cell, key_len, result, bitarray(''))
    return result
