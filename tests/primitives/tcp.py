import socket
import time

from crypto import Server, result, enc_cipher, dec_cipher
from ping_pong import get_ping_request, parse_pong

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

s.connect((Server.host, Server.port))
print('connected')
print('sending:', result)
s.send(result)
print('sent')
data = s.recv(1024)
print('Received', data)
print(dec_cipher.decrypt(data))

ping_result = get_ping_request()
print('sending:', ping_result)
s.send(ping_result)

data = s.recv(1024)
parse_pong(data)


if __name__ == '__main__':
    pass
