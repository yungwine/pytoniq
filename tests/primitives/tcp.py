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

start = time.time()
qids = []
amount = 6000
for i in range(amount):
    ping_result, qid = get_ping_request()
    print('sending:', ping_result)
    s.send(ping_result)
    qids.append(qid)

for i in range(amount):
    data = s.recv(80)
    data = dec_cipher.decrypt(data)
    parse_pong(data, qids[i])


if __name__ == '__main__':
    print(time.time() - start)  # less than 1 sec for 500 ping-pong requests!
