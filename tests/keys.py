from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import dh
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


def get_shared(priv, pub):
    shared = x25519.X25519PrivateKey.from_private_bytes(priv).exchange(x25519.X25519PublicKey.from_public_bytes(pub))
    return shared


if __name__ == '__main__':
    pass