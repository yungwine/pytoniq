import typing

import hashlib
import x25519

from nacl.signing import SigningKey as ed25519Private, VerifyKey as ed25519Public
from nacl.public import PublicKey as x25519Public, PrivateKey as x25519Private

from Cryptodome.Random import get_random_bytes
from Cryptodome.Cipher import AES


class Server:
    def __init__(self, host: str, port: int, pub_key: bytes, magic: bytes = b'\xc6\xb4\x13\x48'):
        self.host = host
        self.port = port
        self.ed25519_public = ed25519Public(pub_key)
        self.x25519_public = self.ed25519_public.to_curve25519_public_key()
        self.magic = magic

    def get_key_id(self):
        return hashlib.sha256(self.magic + self.ed25519_public.encode()).digest()


class Client:
    def __init__(self, ed25519_private_key: bytes) -> None:
        self.ed25519_private = ed25519Private(ed25519_private_key)
        self.ed25519_public = self.ed25519_private.verify_key
        self.x25519_private = self.ed25519_private.to_curve25519_private_key()
        self.x25519_public = self.x25519_private.public_key

    @staticmethod
    def generate_ed25519_private_key() -> bytes:
        return bytes(ed25519Private.generate())


def get_random(bytes_size: int) -> bytes:
    return get_random_bytes(bytes_size)


def create_aes_ctr_cipher(key: bytes, iv: bytes):
    if len(key) != 32:
        raise Exception('key should be 32 bytes exactly!')

    cipher = AES.new(key, AES.MODE_CTR, initial_value=iv, nonce=b'')
    # cipher = Cipher(algorithms.AES(key), modes.CTR(iv)).encryptor()

    return cipher


def aes_ctr_encrypt(cipher, data: bytes) -> bytes:
    # return cipher.encryptor().update(data)
    return cipher.encrypt(data)


def aes_ctr_decrypt(cipher, data: bytes) -> bytes:
    # return cipher.decryptor().update(data)
    return cipher.decrypt(data)


def get_shared_key(private_key: bytes, public_key: bytes) -> bytes:
    """
    :param public_key: peer public x25519 key
    :param private_key: client private x25519 key
    :return: ECDH x25519 shared key
    """
    return x25519.scalar_mult(private_key, public_key)
