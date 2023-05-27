import base64

from nacl.signing import SigningKey
from nacl.signing import SigningKey as EdPrivate, VerifyKey as EdPublic
from nacl.bindings import crypto_sign_ed25519_sk_to_pk
from nacl.public import Box, PublicKey as CurvePublic, PrivateKey as CurvePrivate

from Cryptodome.Random import get_random_bytes
from Cryptodome.Cipher import AES
from Cryptodome.Util import Counter

from hashlib import sha256

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from keys import get_shared


class Server:
    host = '65.21.141.231'
    port = 17728

    pub_key_b64 = 'BYSVpL7aPk0kU5CtlsIae/8mf2B/NrBi7DKmepcjX6Q='

    pub_key = base64.b64decode(pub_key_b64)

    ed25519_public = EdPublic(pub_key)
    x25519_public = ed25519_public.to_curve25519_public_key()


class Client:
    ed25519_private = EdPrivate.generate()
    # ed25519_private = EdPrivate(b'\xf2\x12\x85\x95\xf7*a\x7f\x0f\xf6\x89p\xe3\xf6\xfbJ\xf6[\x12|:\xe4\x81\x1b$D\xf3\x91\x10\xbe\x18!')
    ed25519_public = ed25519_private.verify_key
    x25519_private = ed25519_private.to_curve25519_private_key()
    x25519_public = x25519_private.public_key
    # secret_key = bytes(sk)
    # public_key = bytes(pk)


rand = get_random_bytes(160)
# rand = b'\xa3E\t\xb83(\xb1\xad\x84\xd6\xde\xfa\xb8\x1b\xec>\x88\xb6\x10\x9c,\xf06\x1b\x0c1\xe7\xcdj\x88Z\xd5\xdd\xac\xeeT\rY\x00\rStnS\xd4\xb5t\xc1\xec\x9bAX\xf21\x1d\x8b\xb8\xdeela0-\xb6Y80\xb4T(\xd9\x17O\xff\xd4\x05#BY\xfc@\xb0\x05\xde\x03}<ds\x11a/\x0c\xe7\xed;\nI\xda\xff\xee\\\xaa\x97]\xeb\x84\xac\x82P\xa7\x8eU\r_\x1a\x90\x19h\xae\x15Q\x1d\xe4\xff9\xae\xec\xf00\xafM\xc9\\1pY+*\xd5\xe3\xee\n2\x07\xf2PW\xf8B\x89\x82\xdeJK\x10\x9c\xe1C!'

dec_cipher = AES.new(rand[0:32], AES.MODE_CTR, initial_value=rand[64:80], nonce=b'')
dec_cipher2 = Cipher(algorithms.AES(rand[0:32]), modes.CTR(rand[64:80])).decryptor()

enc_cipher = AES.new(rand[32:64], AES.MODE_CTR, initial_value=rand[80:96], nonce=b'')
enc_cipher2 = Cipher(algorithms.AES(rand[32:64]), modes.CTR(rand[80:96])).encryptor()


checksum = sha256(rand).digest()

key_id = sha256(b'\xc6\xb4\x13\x48' + Server.pub_key).digest()

# shared_key = Box(Client.x25519_private, Server.x25519_public).shared_key()
shared_key = get_shared(bytes(Client.x25519_private), bytes(Server.x25519_public))
# print('shared', shared_key)

init_cipher = AES.new(shared_key[0:16] + checksum[16:32],
                      AES.MODE_CTR,
                      initial_value=checksum[0:4] + shared_key[20:32],
                      nonce=b'')

data = init_cipher.encrypt(rand)

result = key_id + bytes(Client.ed25519_public) + checksum + data

if __name__ == '__main__':
    pass