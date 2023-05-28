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
    # while True:
    is_listening = True

    if queue.qsize() == 0:
        await asyncio.sleep(1)
    for i in range(queue.qsize()):
        data = await reader.read(80)
        queue.get().set_result(dec_cipher.decrypt(data))
    is_listening = False
    # for i in queue:
    #     data = await reader.read(80)
    #     i.set_result(dec_cipher.decrypt(data))


queue = Queue()
amount = 500
is_listening = False


async def ping(writer, reader):
    global queue
    ping_result, qid = get_ping_request()
    # print(qid)
    await send(writer, ping_result)
    cor_result = asyncio.get_running_loop().create_future()
    # queue.append(cor_result)
    queue.put(cor_result)
    if not is_listening:
        await listen(reader)
    # cor_result.set_result(True)
    await cor_result
    if not is_listening:
        await listen(reader)

    parse_pong(cor_result.result(), qid)
    print('Passed!')


async def main():
    reader, writer = await asyncio.open_connection(Server.host, Server.port)
    await send(writer, result)

    data = await recieve(reader, 100)
    print(dec_cipher.decrypt(data))

    # await ping(writer, reader)
    start = time.time()
    tasks = [ping(writer, reader) for _ in range(amount)]
    # await listen(reader)
    await asyncio.gather(*tasks)
    print(time.time() - start)

if __name__ == '__main__':
    asyncio.run(main())
