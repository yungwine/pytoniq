import timeit


schema = b'tcp.ping random_id:long = tcp.Pong'
# schema = b'abcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdwwabcsdww'

code1 = f'''
hex(binascii.crc32({schema}))
'''

code2 = f'''
hex(zlib.crc32({schema}))
'''

code3 = f'''
hex(fastcrc.crc32.iso_hdlc({schema}))
'''

number = 10**6

t1 = timeit.timeit(code1, number=number, setup='import binascii')
t2 = timeit.timeit(code2, number=number, setup='import zlib')
t3 = timeit.timeit(code3, number=number, setup='import fastcrc')

result = {
    'binascii': t1,
    'zlib': t2,
    'fastcrc': t3
}


if __name__ == '__main__':
    print('\n'.join([i[0] + ': ' + str(i[1]) for i in result.items()]))
    print('winner: ', sorted(result.items(), key=lambda i: i[1])[0][0])
    # the winner is usually zlib and sometimes binascii
