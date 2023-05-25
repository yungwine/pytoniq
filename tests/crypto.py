import base64

from nacl.signing import SigningKey
from nacl.bindings import crypto_sign_ed25519_sk_to_pk
from nacl.public import Box, PublicKey, PrivateKey

from Cryptodome.Random import get_random_bytes
from Cryptodome.Cipher import AES
from Cryptodome.Util import Counter

from hashlib import sha256


class Server:
    host = '65.21.141.231'
    port = 17728

    pub_key_b64 = 'BYSVpL7aPk0kU5CtlsIae/8mf2B/NrBi7DKmepcjX6Q='

    pub_key = base64.b64decode(pub_key_b64)
    pk = PublicKey(pub_key)


class Client:
    sk = PrivateKey.generate()
    pk = sk.public_key
    secret_key = bytes(sk)
    public_key = bytes(pk)


rand = get_random_bytes(160)

enc_cipher = AES.new(rand[0:32], AES.MODE_CTR, initial_value=rand[64:80], nonce=b'')

dec_cipher = AES.new(rand[32:64], AES.MODE_CTR, initial_value=rand[80:96], nonce=b'')

checksum = sha256(rand).digest()

key_id = sha256(b'\xc6\xb4\x13\x48' + Server.pub_key).digest()

shared_key = Box(Client.sk, Server.pk).shared_key()

init_cipher = AES.new(shared_key[0:16] + checksum[16:32],
                      AES.MODE_CTR,
                      initial_value=checksum[0:4] + shared_key[20:32],
                      nonce=b'')

data = init_cipher.encrypt(rand)

result = key_id + Client.public_key + checksum + data


if __name__ == '__main__':
    # print(Client.secret_key, Client.public_key, rand)
    print(checksum)
    print(len(bytes(shared_key)))
    print(result)
    print(len(result))
