"""By psylopunk with some changes"""

import typing

from ..builder import Builder


def pad(src: str, size: int) -> str:
    while len(src) < size:
        src = '0' + src
    return src


def remove_prefix_map(src: dict, length: int) -> dict:
    if length == 0:
        return src
    else:
        res = {}
        for k in src:
            res[k[length:]] = src[k]

        return res


def find_common_prefix(src: list) -> str:
    # Corner cases
    if len(src) == 0:
        return ''
    if len(src) == 1:
        return src[0]

    # Searching for prefix
    _sorted = sorted(src)
    size = 0
    for i, e in enumerate(_sorted[0]):
        if e == _sorted[-1][i]:
            size += 1
        else:
            break

    return _sorted[0][:size]


def fork_map(src: dict) -> typing.Tuple[dict, dict]:
    assert len(src) > 0, 'Internal inconsistency'
    left = {}
    right = {}
    for k in src:
        if k.find('0') == 0:
            left[k[1:]] = src[k]
        else:
            right[k[1:]] = src[k]

    assert len(left) > 0, 'Internal inconsistency. Left empty.'
    assert len(right) > 0, 'Internal inconsistency. Left empty.'
    return left, right


def build_node(src: dict) -> dict:
    assert len(src) > 0, 'Internal inconsistency'
    if len(src) == 1:
        return {
            'type': 'leaf',
            'value': list(src.values())[0]
        }

    left, right = fork_map(src)
    return {
        'type': 'fork',
        'left': build_edge(left),
        'right': build_edge(right)
    }


def build_edge(src: dict) -> dict:
    assert len(src) > 0, 'Internal inconsistency'
    label = find_common_prefix(list(src.keys()))
    return {
        'label': label,
        'node': build_node(
            remove_prefix_map(src, len(label))
        )
    }


def build_tree(src: dict, key_size: int) -> dict:
    # Convert map keys
    tree = {}
    for key in src:
        padded = pad(bin(key)[2:], key_size)
        tree[padded] = src[key]

    # Calculate root label
    return build_edge(tree)


# Serialization
def write_label_short(src: dict, to: Builder) -> Builder:
    # Header
    to.store_bit_int(0)

    # Unary length
    for _ in src:
        to.store_bit_int(1)
    to.store_bit_int(0)

    # Value
    for e in src:
        to.store_bit_int(e == '1')

    return to


def label_short_length(src: dict) -> int:
    return 1 + len(src) + 1 + len(src)


def write_label_long(src, key_length, to: Builder) -> Builder:
    # Header
    to.store_bit_int(1)
    to.store_bit_int(0)

    # Length
    length = key_length.bit_length()
    to.store_uint(len(src), length)

    # Value
    for e in src:
        to.store_bit_int(e == '1')

    return to


def label_long_length(src: dict, key_length: int) -> int:
    return 1 + 1 + key_length.bit_length() + len(src)


def write_label_same(value: bool, length, key_length, to: Builder) -> None:
    to.store_bit_int(1)
    to.store_bit_int(1)

    to.store_bit_int(value)

    len_len = key_length.bit_length()
    to.store_uint(length, len_len)


def label_same_length(key_size: int) -> int:
    return 1 + 1 + 1 + key_size.bit_length()


def is_same(src) -> bool:
    if len(src) == 0 or len(src) == 1:
        return True

    for e in src[1:]:
        if e != src[0]:
            return False

    return True


def detect_label_type(src: dict, key_size: int) -> str:
    kind = 'short'
    kind_length = label_short_length(src)

    long_length = label_long_length(src, key_size)
    if long_length < kind_length:
        kind_length = long_length
        kind = 'long'

    if is_same(src):
        same_length = label_same_length(key_size)
        if same_length < kind_length:
            kind_length = same_length
            kind = 'same'
    return kind


def write_label(src: dict, key_size: int, to: Builder) -> None:
    type_ = detect_label_type(src, key_size)
    if type_ == 'short':
        write_label_short(src, to)
    elif type_ == 'long':
        write_label_long(src, key_size, to)
    elif type_ == 'same':
        write_label_same(src[0] == '1', len(src), key_size, to)


def write_node(src: dict, key_size: int, serializer: typing.Callable, to: Builder) -> None:
    if src['type'] == 'leaf':
        serializer(src['value'], to)

    if src['type'] == 'fork':
        left_cell = Builder()
        right_cell = Builder()
        write_edge(src['left'], key_size - 1, serializer, left_cell)
        write_edge(src['right'], key_size - 1, serializer, right_cell)
        to.store_ref(left_cell.end_cell())
        to.store_ref(right_cell.end_cell())


def write_edge(src: dict, key_size: int, serializer: typing.Callable, to: Builder) -> None:
    write_label(src['label'], key_size, to)
    write_node(src['node'], key_size - len(src['label']), serializer, to)


def serialize_dict(src: dict, key_size: int, serializer: typing.Callable) -> Builder:
    tree = build_tree(src, key_size)
    dest = Builder()
    write_edge(tree, key_size, serializer, dest)
    return dest
