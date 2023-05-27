import base64
import hashlib
import socket
import typing

# from .crypto import ed25519Public, ed25519Private, x25519Public, x25519Private
from .crypto import Server, Client, get_random, create_aes_ctr_cipher, aes_ctr_encrypt, aes_ctr_decrypt, get_shared_key


class AdnlClientTcp:

    def __init__(self,
                 host: str,  # ipv4 host
                 port: int,
                 server_pub_key: str,  # server ed25519 public key in base64,
                 client_private_key: typing.Optional[bytes] = None  # can specify private key, then it's won't be generated
                 ) -> None:
        self.server = Server(host, port, base64.b64decode(server_pub_key))
        if client_private_key is None:
            self.client = Client(Client.generate_ed25519_private_key())  # recommended
        else:
            self.client = Client(client_private_key)

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.enc_sipher = None
        self.dec_sipher = None

    def encrypt(self, data: bytes) -> bytes:
        return aes_ctr_encrypt(self.enc_sipher, data)

    def decrypt(self, data: bytes) -> bytes:
        return aes_ctr_decrypt(self.dec_sipher, data)

    def recieve(self):
        size = self.decrypt(self.socket.recv(4))
        print(size)

    def connect(self) -> None:  # TODO async
        handshake = self.handshake()
        self.socket.connect((self.server.host, self.server.port))
        self.socket.send(handshake)
        self.recieve()


    def handshake(self) -> bytes:
        rand = get_random(160)

        self.dec_sipher = create_aes_ctr_cipher(rand[0:32], rand[64:80])

        self.enc_sipher = create_aes_ctr_cipher(rand[32:64], rand[80:96])

        checksum = hashlib.sha256(rand).digest()

        shared_key = get_shared_key(self.client.x25519_private.encode(), self.server.x25519_public.encode())

        init_cipher = create_aes_ctr_cipher(shared_key[0:16] + checksum[16:32], checksum[0:4] + shared_key[20:32])

        data = aes_ctr_encrypt(init_cipher, rand)

        return self.server.get_key_id() + self.client.ed25519_public.encode() + checksum + data






