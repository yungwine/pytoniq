import socket
from crypto import Server, result

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
print(Server.host, Server.port)
s.connect((Server.host, Server.port))
print('connected')
s.sendall(result)
print('sent')
data = s.recv(1000)
s.close()
print('Received', repr(data))

if __name__ == '__main__':
    pass
