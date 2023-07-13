import typing

from .block import CurrencyCollection
from .tlb import TlbScheme, TlbError
from .account import AccountStatus, StateInit, StorageUsedShort
from .utils import HashUpdate
from ..boc import Slice, Builder, Cell
from ..boc.address import Address


class ConfigError(TlbError):
    pass


class CatchainConfig(TlbScheme):
    """
    catchain_config#c1 mc_catchain_lifetime:uint32 shard_catchain_lifetime:uint32
    shard_validators_lifetime:uint32 shard_validators_num:uint32 = CatchainConfig;

    catchain_config_new#c2 flags:(## 7) { flags = 0 } shuffle_mc_validators:Bool
    mc_catchain_lifetime:uint32 shard_catchain_lifetime:uint32
    shard_validators_lifetime:uint32 shard_validators_num:uint32 = CatchainConfig;
    """

    def __init__(self, type_: typing.Literal["catchain_config", "catchain_config_new"],
                 mc_catchain_lifetime: int,
                 shard_catchain_lifetime: int,
                 shard_validators_lifetime: int,
                 shard_validators_num: int,
                 shuffle_mc_validators: typing.Optional[bool] = None,
                 ):
        self.type_ = type_
        self.mc_catchain_lifetime = mc_catchain_lifetime
        self.shard_catchain_lifetime = shard_catchain_lifetime
        self.shard_validators_lifetime = shard_validators_lifetime
        self.shard_validators_num = shard_validators_num
        self.shuffle_mc_validators = shuffle_mc_validators

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_bytes(1)[:1]
        if tag == b'\xc1':
            return cls(
                type_='catchain_config',
                mc_catchain_lifetime=cell_slice.load_uint(32),
                shard_catchain_lifetime=cell_slice.load_uint(32),
                shard_validators_lifetime=cell_slice.load_uint(32),
                shard_validators_num=cell_slice.load_uint(32)
            )
        elif tag == b'\xc2':
            flags = cell_slice.load_uint(7)
            assert flags == 0
            return cls(
                type_='catchain_config_new',
                shuffle_mc_validators=cell_slice.load_bool(),
                mc_catchain_lifetime=cell_slice.load_uint(32),
                shard_catchain_lifetime=cell_slice.load_uint(32),
                shard_validators_lifetime=cell_slice.load_uint(32),
                shard_validators_num=cell_slice.load_uint(32)
            )
        else:
            raise ConfigError(f'CatchainConfig deserialization error: unexpected tag {tag}')


class ConfigParam28(CatchainConfig):
    """
    _ CatchainConfig = ConfigParam 28;
    """

    def __init__(self, **kwargs):  # TODO maybe change
        super().__init__(**kwargs)

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return super().deserialize(cell_slice)



class ConfigParam34(TlbScheme):
    """
    _ cur_validators:ValidatorSet = ConfigParam 34;
    """

    def __init__(self, cur_validators: "ValidatorSet"):
        self.cur_validators = cur_validators

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(cur_validators=ValidatorSet.deserialize(cell_slice))


class SigPubKey(TlbScheme):
    """
    ed25519_pubkey#8e81278a pubkey:bits256 = SigPubKey;  // 288 bits
    """
    def __init__(self, pubkey: bytes):
        self.pubkey = pubkey

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_bytes(4)
        if tag != b"\x8e\x81'\x8a":
            raise ConfigError(f'SigPubKey deserialization error: unexpected tag {tag}')
        return cls(cell_slice.load_bytes(32))


class ValidatorDescr(TlbScheme):
    """
    validator#53 public_key:SigPubKey weight:uint64 = ValidatorDescr;
    validator_addr#73 public_key:SigPubKey weight:uint64 adnl_addr:bits256 = ValidatorDescr;
    """
    def __init__(self,
                 type_: str,
                 public_key: SigPubKey,
                 weight: int,
                 adnl_addr: typing.Optional[bytes] = None
                 ):
        self.type_ = type_
        self.public_key = public_key
        self.weight = weight
        self.adnl_addr = adnl_addr

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_bytes(1)[:1]
        if tag not in (b'\x53', b'\x73'):
            raise ConfigError(f'ValidatorDescr deserialization error: unexpected tag {tag}')
        public_key = SigPubKey.deserialize(cell_slice)
        weight = cell_slice.load_uint(64)
        adnl_addr = None
        type_ = 'validator'
        if tag == b'\x73':
            type_ = 'validator_addr'
            adnl_addr = cell_slice.load_bytes(32)
        return cls(
            type_=type_,
            public_key=public_key,
            weight=weight,
            adnl_addr=adnl_addr
        )


class ValidatorSet(TlbScheme):
    """
    validators#11 utime_since:uint32 utime_until:uint32
    total:(## 16) main:(## 16) { main <= total } { main >= 1 }
    list:(Hashmap 16 ValidatorDescr) = ValidatorSet;

    validators_ext#12 utime_since:uint32 utime_until:uint32
    total:(## 16) main:(## 16) { main <= total } { main >= 1 }
    total_weight:uint64 list:(HashmapE 16 ValidatorDescr) = ValidatorSet;
    """

    def __init__(self,
                 type_: str,
                 utime_since: int,
                 utime_until: int,
                 total: int,
                 main: int,
                 total_weight: typing.Optional[int],
                 list: typing.Dict[int, "ValidatorDescr"]
                 ):

        self.type_ = type_
        self.utime_since = utime_since
        self.utime_until = utime_until
        self.total = total
        self.main = main
        self.total_weight = total_weight
        self.list = list

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_bytes(1)[:1]
        if tag not in (b'\x11', b'\x12'):
            raise ConfigError(f'ValidatorSet deserialization error: unknown prefix tag: {tag}')
        utime_since = cell_slice.load_uint(32)
        utime_until = cell_slice.load_uint(32)
        total = cell_slice.load_uint(16)
        main = cell_slice.load_uint(16)

        if not main <= total:
            raise ConfigError(f'expected main <= total, got: main={main}, total={total}')
        if not main >= 1:
            raise ConfigError(f'expected main >= 1, got: main={main}')
        total_weight = None
        type_ = 'validators'
        if tag == b'\x12':
            type_ = 'validators_ext'
            total_weight = cell_slice.load_uint(64)
        list = cell_slice.load_dict(16, value_deserializer=ValidatorDescr.deserialize)

        return cls(
            type_=type_,
            utime_since=utime_since,
            utime_until=utime_until,
            total=total,
            main=main,
            total_weight=total_weight,
            list=list
        )


class ConfigParam(TlbScheme):

    params = {
        34: ConfigParam34
    }

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, *args):
        pass


