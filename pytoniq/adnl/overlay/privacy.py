import time
import typing
import enum

from pytoniq_core.tl import TlSchemas, TlGenerator
from pytoniq_core.crypto.signature import verify_sign


class BroadcastCheckResult(enum.Enum):
    Forbidden = 1
    NeedCheck = 2
    Allowed = 3


class OverlayPrivacyRules:

    def __init__(
            self,
            max_unauth_size: int,
            flags: int,
            authorized_keys: typing.Dict[bytes, int]
    ):
        """
        :param max_unauth_size: maximum broadcast without authorization bytes length
        :param flags:
        :param authorized_keys: {key: max_size}
        """
        self.max_unauth_size = max_unauth_size
        self.flags = flags
        self.authorized_keys = authorized_keys

    @classmethod
    def default(cls, allow_fec: bool):
        return cls(
            max_unauth_size=16 << 20,
            flags=int(allow_fec),
            authorized_keys={}
        )

    @property
    def allow_fec(self) -> bool:
        return bool(self.flags & 1)

    def check_rules(self, key_id: bytes, size: int, is_fec: bool) -> BroadcastCheckResult:
        if key_id not in self.authorized_keys:
            if size > self.max_unauth_size:
                return BroadcastCheckResult.Forbidden
            if not(self.flags & 1) and is_fec:
                return BroadcastCheckResult.Forbidden
            return BroadcastCheckResult.Allowed if self.flags & 2 else BroadcastCheckResult.NeedCheck
        return BroadcastCheckResult.Allowed if size <= self.authorized_keys[key_id] else BroadcastCheckResult.Forbidden


class InvalidCertificate(Exception):
    pass


class Certificate:
    def __init__(
            self,
            data: dict,
            schemes: TlSchemas = None
    ):
        self._data = data
        if schemes is None:
            schemes = TlGenerator.with_default_schemas().generate()
        self._schemes = schemes

    @property
    def flags(self):
        return self._data.get('flags', self.get_cert_default_flags(self._data['max_size']))

    @staticmethod
    def get_cert_default_flags(max_size: int) -> int:
        return (1 if max_size > 768 else 0) | 2  # allowFec if max_size > 768 else 0

    def to_sign(self, overlay_id: bytes, issued_to: bytes) -> bytes:
        """
        overlay.certificateId overlay_id:int256 node:int256 expire_at:int max_size:int = overlay.CertificateId;
        overlay.certificateIdV2 overlay_id:int256 node:int256 expire_at:int max_size:int flags:int = overlay.CertificateId;
        """
        if self.flags == self.get_cert_default_flags(self._data['max_size']):
            data = {'overlay_id': overlay_id.hex(), 'node': issued_to.hex(), 'expire_at': self._data['expire_at'], 'max_size': self._data['max_size']}
            return self._schemes.serialize('overlay.certificateId', data)
        data = {'overlay_id': overlay_id.hex(), 'node': issued_to.hex(), 'expire_at': self._data['expire_at'], 'max_size': self._data['max_size'], 'flags': self._data['flags']}
        return self._schemes.serialize('overlay.certificateIdV2', data)

    def check(self, node_id: bytes, overlay_id: bytes, size: int, is_fec: bool) -> BroadcastCheckResult:
        """
        overlay.certificateV2 issued_by:PublicKey expire_at:int max_size:int flags:int signature:bytes = overlay.Certificate;
        """
        if size > self._data['max_size']:
            return BroadcastCheckResult.Forbidden

        if time.time() > self._data['expire_at']:
            return BroadcastCheckResult.Forbidden

        if is_fec and not(self.flags & 1):
            return BroadcastCheckResult.Forbidden

        pub_key = bytes.fromhex(self._data['issued_by']['key'])

        to_sign = self.to_sign(overlay_id, node_id)
        if not verify_sign(pub_key, to_sign, self._data['signature']):
            return BroadcastCheckResult.Forbidden

        return BroadcastCheckResult.Allowed if self.flags & 2 else BroadcastCheckResult.NeedCheck
