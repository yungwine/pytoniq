import asyncio
import time
from queue import Queue

from crypto import Server, result, enc_cipher, dec_cipher
from ping_pong import get_ping_request, parse_pong


async def send(writer, data: bytes):
    print(f'Send: {data}')
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
    global is_listening
    while True:
        if queue.qsize() == 0:
            await asyncio.sleep(0.1)
            continue

        for i in range(queue.qsize()):
            data = await reader.read(80)
            queue.get().set_result(dec_cipher.decrypt(data))


queue = Queue()
amount = 5000
is_listening = False


async def ping(writer):
    global queue
    ping_result, qid = get_ping_request()
    await send(writer, ping_result)
    cor_result = asyncio.get_running_loop().create_future()
    queue.put(cor_result)
    await cor_result
    parse_pong(cor_result.result(), qid)
    print('Passed!')


async def main():
    reader, writer = await asyncio.open_connection(Server.host, Server.port)
    await send(writer, result)

    data = await recieve(reader, 100)
    print(dec_cipher.decrypt(data))

    # await ping(writer, reader)
    start = time.time()
    tasks = [ping(writer) for _ in range(amount)]
    asyncio.create_task(listen(reader))
    await asyncio.gather(*tasks)
    print(time.time() - start)


if __name__ == '__main__':
    asyncio.run(main())
