from nacl.signing import VerifyKey, exc


def verify_sign(public_key: bytes, signed_message: bytes, signature: bytes):
    key = VerifyKey(public_key)
    try:
        key.verify(signed_message, signature)
        return True
    except exc.BadSignatureError:
        return False
