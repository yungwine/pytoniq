import typing


def make_url_safe(str: str) -> str:
    return str.replace("+", '-').replace("/", '_')


def bytes_to_uint(data: bytes):
    return int.from_bytes(data, 'big', signed=False)


def bin_to_signed_int(ba: str) -> int:
    from bitstring import BitArray
    return BitArray(bin=ba).int
