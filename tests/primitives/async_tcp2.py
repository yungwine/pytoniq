import asyncio
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
amount = 5


def send(future):
    global qids
    ping_result, qid = get_ping_request()
    print('sending:', ping_result)
    s.send(ping_result)
    future.set_result(True)
    qids.append(qid)


def recieve(i):
    data = s.recv(80)
    print('recieved:', data)
    data = dec_cipher.decrypt(data)
    print(i)
    parse_pong(data, qids[i])


async def ping(i):
    future = asyncio.get_event_loop().create_future()
    asyncio.get_event_loop().run_in_executor(None, lambda: send(future))
    await future
    asyncio.get_event_loop().run_in_executor(None, lambda: recieve(i))


async def main():
    start = time.time()
    tasks = [ping(i) for i in range(amount)]
    # await listen(reader)
    await asyncio.gather(*tasks)
    print(time.time() - start)


if __name__ == '__main__':
    asyncio.run(main())
