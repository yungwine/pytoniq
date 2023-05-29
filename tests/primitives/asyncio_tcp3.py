import asyncio
import hashlib
import time
from queue import Queue

from crypto import Server, result, enc_cipher, dec_cipher, get_random_bytes
from ping_pong import get_ping_request, parse_pong


async def send(writer, data: bytes, i=None):
    print(f'Send: {i}')
    writer.write(data)
    await writer.drain()


async def recieve(reader, len: int):
    data = await reader.read(len)
    print(f'Received: {data}')
    return data


async def close(writer):
    print('Close the connection')
    writer.close()
    await writer.wait_closed()


async def listen(reader):
    while True:
        if queue.qsize() == 0:
            await asyncio.sleep(0.1)
            continue

        for i in range(queue.qsize()):
            data = await reader.read(4)
            l = int(dec_cipher.decrypt(data)[::-1].hex(), 16)
            print(i, l)
            data = await reader.read(l)
            queue.get().set_result(dec_cipher.decrypt(data))


queue = Queue()
amount = 1000


async def ping(writer):
    global queue
    ping_result, qid = get_ping_request()
    await send(writer, ping_result)
    cor_result = asyncio.get_running_loop().create_future()
    queue.put(cor_result)
    await cor_result
    parse_pong(cor_result.result(), qid)
    print('Passed!')


async def get_masterchain_info(writer, i):
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

    await send(writer, enc_cipher.encrypt(data), i)
    cor_result = asyncio.get_running_loop().create_future()
    queue.put(cor_result)
    await cor_result
    # print(cor_result.result())


async def main():
    reader, writer = await asyncio.open_connection(Server.host, Server.port)
    await send(writer, result)

    data = await recieve(reader, 100)
    print(dec_cipher.decrypt(data))

    # await ping(writer, reader)
    start = time.time()
    tasks = [get_masterchain_info(writer, i) for i in range(amount)]
    asyncio.create_task(listen(reader))
    await asyncio.gather(*tasks)
    print(time.time() - start)


if __name__ == '__main__':
    asyncio.run(main())
