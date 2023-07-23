from nacl.signing import VerifyKey, exc, SignedMessage
from nacl.bindings import crypto_sign, crypto_sign_BYTES
import nacl.encoding



def verify_sign(public_key: bytes, signed_message: bytes, signature: bytes):
    key = VerifyKey(public_key)
    try:
        key.verify(signed_message, signature)
        return True
    except exc.BadSignatureError:
        return False


def sign_message(message: bytes,
                 signing_key,
                 encoder: nacl.encoding.Encoder = nacl.encoding.RawEncoder, ) -> bytes:
    raw_signed = crypto_sign(message, signing_key)

    signature = encoder.encode(raw_signed[:crypto_sign_BYTES])
    message = encoder.encode(raw_signed[crypto_sign_BYTES:])
    signed = encoder.encode(raw_signed)

    return SignedMessage._from_parts(signature, message, signed).signature
