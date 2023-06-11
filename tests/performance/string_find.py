import timeit
import random
import string
import re

letters = string.ascii_lowercase + ';' + '(' + ')' + ' '

string = ''.join(random.choice(letters) for i in range(1000))

code1 = '''
if '#' in string:
    print('yes')
'''

code2 = f'''
for i in string:
    if i is '#':
        print('yes')
        break
'''


number = 10**5
t1 = timeit.timeit(code1, number=number, globals=globals())
t2 = timeit.timeit(code2, number=number, globals=globals())

result = {
    'in': t1,
    'for': t2,
}

if __name__ == '__main__':
    print(result)
    print('winner: ', sorted(result.items(), key=lambda i: i[1])[0][0])
    # the winner is .replace()
