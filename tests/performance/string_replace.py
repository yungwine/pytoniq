import timeit
import random
import string
import re

# printing lowercase
letters = string.ascii_lowercase + ';' + '(' + ')' + ' '

string = ''.join(random.choice(letters) for i in range(1000))

code1 = '''
string.replace(';', '').replace('(', '').replace(')', '')
'''

code2 = f'''
new_schema = ''
restricted = {';', '(', ')'}
for c in string:
    if c not in restricted:
        new_schema += c
'''

code3 = f'''
re.sub('\(|\)|;', '', string)
'''

number = 10**4 * 3
t1 = timeit.timeit(code1, number=number, globals=globals())
t2 = timeit.timeit(code2, number=number, globals=globals())
t3 = timeit.timeit(code3, number=number, globals=globals())

result = {
    'replace': t1,
    'clear': t2,
    're': t3
}

if __name__ == '__main__':
    print(result)
    print('winner: ', sorted(result.items(), key=lambda i: i[1])[0][0])
    # the winner is .replace()
