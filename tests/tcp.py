import socket
import time

from crypto import Server, result, enc_cipher, dec_cipher
from ping_pong import ping_result, parse_pong

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

s.connect((Server.host, Server.port))
print('connected')
s.sendall(result)
print('sent')
data = s.recv(1024)
print('Received', data)


s.sendall(ping_result)
size = s.recv(1024)
print('Received', size)

parse_pong(size)
