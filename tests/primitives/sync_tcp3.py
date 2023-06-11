import asyncio
import hashlib
import socket
import time
from queue import Queue

from crypto import Server, result, enc_cipher, dec_cipher, dec_cipher2, get_random_bytes
from ping_pong import get_ping_request, parse_pong


def get_masterchain_info():
    data = 0x74.to_bytes(byteorder='little', length=4)  # length
    nonce = get_random_bytes(32)
    data += nonce
    data += 0x7af98bb4.to_bytes(byteorder='big', length=4)
    data += get_random_bytes(32)
    data += b'\x0c'
    data += b'\xdf\x06\x8c\x79'
    data += b'\x04'
    data += b'\x2e\xe6\xb5\x89'
    data += b'\x00\x00\x00'
    data += b'\x00\x00\x00'
    data += hashlib.sha256(data[4:]).digest()
    return data


def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
    s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    s.connect((Server.host, Server.port))
    print('sending:', result)
    s.send(result)
    data = s.recv(1024)
    print('Received', data)
    print(dec_cipher2.update(data))
    print('connected')

    amount = 5000
    for i in range(amount):
        ping_result = get_masterchain_info()
        print('sending:', ping_result)
        data = enc_cipher.encrypt(ping_result)
        print(data)
        s.send(data)
    count = 0
    buffer = bytearray(2**32)

    for i in range(amount):
        if i >= 1500:
            time.sleep(0.05)
        s.recv_into(buffer, 4)
        print(i)
        # data = s.recvmsg(4, 1)
        data = buffer[:4]
        del buffer[:4]
        dlen = dec_cipher2.update(data)
        dlen = int(dlen[:4][::-1].hex(), 16)
        print(dlen)
        s.recv_into(buffer, dlen)
        data = dec_cipher2.update(buffer[:dlen])
        del buffer[:dlen]
        print(len(data))


if __name__ == '__main__':
    main()
