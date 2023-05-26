import struct
import time

from bitarray import bitarray

from Cryptodome.Random import get_random_bytes
from hashlib import sha256

from crypto import enc_cipher, dec_cipher, dec_cipher2
# from tcp import s, enc_cipher, dec_cipher


data = b'\x00\x00\x00\x4c'[::-1]
# data = 0x4c.to_bytes(byteorder='little', length=4)  # length


nonce = get_random_bytes(32)

data += nonce

data += b'\x4d\x08\x2b\x9a'[::-1]  # TL id
# data += 0x9a2b084d.to_bytes(byteorder='big', length=4)

query_id = get_random_bytes(8)

data += query_id[::-1]


hash = sha256(data[4:]).digest()  # checksum
data += hash
ping_result = enc_cipher.encrypt(data)
# ping_result =
print(len(data))


def parse_pong(data: bytes):
    data_decr = dec_cipher.decrypt(data)
    # data_decr = dec_cipher2.update(data) + dec_cipher2.finalize()
    print('decrypted', data_decr)
    a = bitarray()
    a.frombytes(data_decr)
    print(a[:32])
    print(data_decr.hex())
    size = int(data_decr[:4][::-1].hex(), 16)
    actual_size = len(data_decr) - 4
    print(size, actual_size)

    # assert size == actual_size
    # del data[:4]
    print(data[36:40])
