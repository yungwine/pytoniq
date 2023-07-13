import typing

from .block import CurrencyCollection, ExtraCurrencyCollection, GlobalVersion
from .tlb import TlbScheme, TlbError
from .account import AccountStatus, StateInit, StorageUsedShort
from .utils import HashUpdate
from ..boc import Slice, Builder, Cell
from ..boc.address import Address


class ConfigError(TlbError):
    pass


class ConfigParam0(TlbScheme):
    """
    _ config_addr:bits256 = ConfigParam 0;
    """
    def __init__(self, config_addr: bytes):
        self.config_addr = config_addr
        self.config_addr_hex = config_addr.hex()

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(cell_slice.load_bytes(32))

    # def __repr__(self):
    #     d = self.__dict__
    #     d.pop('config_addr')
    #     return f'{d}'


class ConfigParam1(TlbScheme):
    """
    _ elector_addr:bits256 = ConfigParam 1;
    """
    def __init__(self, elector_addr: bytes):
        self.elector_addr = elector_addr
        self.elector_addr_hex = elector_addr.hex()

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(cell_slice.load_bytes(32))


class ConfigParam2(TlbScheme):
    """
    _ minter_addr:bits256 = ConfigParam 2;  // ConfigParam 0 is used if absent
    """
    def __init__(self, minter_addr: bytes):
        self.minter_addr = minter_addr
        self.minter_addr_hex = minter_addr.hex()

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(cell_slice.load_bytes(32))


class ConfigParam3(TlbScheme):
    """
    _ fee_collector_addr:bits256 = ConfigParam 3;  // ConfigParam 1 is used if absent
    """
    def __init__(self, fee_collector_addr: bytes):
        self.fee_collector_addr = fee_collector_addr
        self.fee_collector_addr_hex = fee_collector_addr.hex()

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(cell_slice.load_bytes(32))


class ConfigParam4(TlbScheme):
    """
    _ dns_root_addr:bits256 = ConfigParam 4;  // root TON DNS resolver
    """
    def __init__(self, dns_root_addr: bytes):
        self.dns_root_addr = dns_root_addr
        self.dns_root_addr_hex = dns_root_addr.hex()

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(cell_slice.load_bytes(32))


class ConfigParam5(TlbScheme):
    """
    burning_config#01
    blackhole_addr:(Maybe bits256)
    fee_burn_nom:# fee_burn_denom:# { fee_burn_nom <= fee_burn_denom } { fee_burn_denom >= 1 } = BurningConfig;
    _ BurningConfig = ConfigParam 5;
    """
    def __init__(self,
                 blackhole_addr: typing.Optional[bytes],
                 fee_burn_nom: int,
                 fee_burn_denom: int,
                 ):
        self.blackhole_addr = blackhole_addr
        if blackhole_addr:
            self.blackhole_addr_hex = blackhole_addr.hex()
        self.fee_burn_nom = fee_burn_nom
        self.fee_burn_denom = fee_burn_denom

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_bytes(1)[:1]
        if tag != b'\x01':
            raise ConfigError(f'BurningConfig deserialization error: unexpected tag {tag}')
        blackhole_addr = cell_slice.load_bytes(32) if cell_slice.load_bit() else None
        fee_burn_nom = cell_slice.load_uint(32)
        fee_burn_denom = cell_slice.load_uint(32)
        return cls(blackhole_addr, fee_burn_nom, fee_burn_denom)


class ConfigParam6(TlbScheme):
    """
    _ mint_new_price:Grams mint_add_price:Grams = ConfigParam 6;
    """
    def __init__(self, mint_new_price: int, mint_add_price: int):
        self.mint_new_price = mint_new_price
        self.mint_add_price = mint_add_price

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(cell_slice.load_coins(), cell_slice.load_coins())


class ConfigParam7(TlbScheme):
    """
    _ to_mint:ExtraCurrencyCollection = ConfigParam 7;
    """
    def __init__(self, to_mint: ExtraCurrencyCollection):
        self.to_mint = to_mint

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(ExtraCurrencyCollection.deserialize(cell_slice))


class ConfigParam8(GlobalVersion):
    """
    _ GlobalVersion = ConfigParam 8;  // all zero if absent
    """
    def __init__(self, **kwargs):  # TODO maybe change
        super().__init__(**kwargs)

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return super().deserialize(cell_slice)


class ConfigParam9(TlbScheme):
    """
    _ mandatory_params:(Hashmap 32 True) = ConfigParam 9;
    """
    def __init__(self, mandatory_params: dict):
        self.mandatory_params = mandatory_params

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(cell_slice.load_hashmap(32, value_deserializer=lambda src: True))


class ConfigParam10(TlbScheme):
    """
    _ critical_params:(Hashmap 32 True) = ConfigParam 10;
    """
    def __init__(self, critical_params: dict):
        self.critical_params = critical_params

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(cell_slice.load_hashmap(32, value_deserializer=lambda src: True))


class ConfigProposalSetup(TlbScheme):
    """
    cfg_vote_cfg#36 min_tot_rounds:uint8 max_tot_rounds:uint8 min_wins:uint8 max_losses:uint8 min_store_sec:uint32 max_store_sec:uint32 bit_price:uint32 cell_price:uint32 = ConfigProposalSetup;
    """
    def __init__(self,
                 min_tot_rounds: int,
                 max_tot_rounds: int,
                 min_wins: int,
                 max_losses: int,
                 min_store_sec: int,
                 max_store_sec: int,
                 bit_price: int,
                 cell_price: int
                 ):

        self.min_tot_rounds = min_tot_rounds
        self.max_tot_rounds = max_tot_rounds
        self.min_wins = min_wins
        self.max_losses = max_losses
        self.min_store_sec = min_store_sec
        self.max_store_sec = max_store_sec
        self.bit_price = bit_price
        self.cell_price = cell_price

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_bytes(1)[:1]
        if tag != b'\x36':
            raise ConfigError(f'ConfigProposalSetup deserialization error: unexpected tag {tag}')
        return cls(
            min_tot_rounds=cell_slice.load_uint(8),
            max_tot_rounds=cell_slice.load_uint(8),
            min_wins=cell_slice.load_uint(8),
            max_losses=cell_slice.load_uint(8),
            min_store_sec=cell_slice.load_uint(32),
            max_store_sec=cell_slice.load_uint(32),
            bit_price=cell_slice.load_uint(32),
            cell_price=cell_slice.load_uint(32)
        )


class ConfigVotingSetup(TlbScheme):
    """
    cfg_vote_setup#91 normal_params:^ConfigProposalSetup critical_params:^ConfigProposalSetup = ConfigVotingSetup;
    """
    def __init__(self, normal_params: ConfigProposalSetup, critical_params: ConfigProposalSetup):
        self.normal_params = normal_params
        self.critical_params = critical_params

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_bytes(1)[:1]
        if tag != b'\x91':
            raise ConfigError(f'ConfigVotingSetup deserialization error: unexpected tag {tag}')
        return cls(
            normal_params=ConfigProposalSetup.deserialize(cell_slice.load_ref().begin_parse()),
            critical_params=ConfigProposalSetup.deserialize(cell_slice.load_ref().begin_parse())
        )


class ConfigParam11(ConfigVotingSetup):
    """
    _ ConfigVotingSetup = ConfigParam 11;
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return super().deserialize(cell_slice)


class WorkchainFormat(TlbScheme):
    """
    wfmt_basic#1 vm_version:int32 vm_mode:uint64 = WorkchainFormat 1;

    wfmt_ext#0 min_addr_len:(## 12) max_addr_len:(## 12) addr_len_step:(## 12)
    { min_addr_len >= 64 } { min_addr_len <= max_addr_len }
    { max_addr_len <= 1023 } { addr_len_step <= 1023 }
    workchain_type_id:(## 32) { workchain_type_id >= 1 }
    = WorkchainFormat 0;
    """

    def __init__(self,
                 type_: typing.Literal["wfmt_basic", "wfmt_ext"],
                 vm_version: typing.Optional[int] = None,
                 vm_mode: typing.Optional[int] = None,
                 min_addr_len: typing.Optional[int] = None,
                 max_addr_len: typing.Optional[int] = None,
                 addr_len_step: typing.Optional[int] = None,
                 workchain_type_id: typing.Optional[int] = None,
                 ):
        self.type_ = type_
        self.vm_version = vm_version
        self.vm_mode = vm_mode
        self.min_addr_len = min_addr_len
        self.max_addr_len = max_addr_len
        self.addr_len_step = addr_len_step
        self.workchain_type_id = workchain_type_id

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice, v: int = 0):
        tag = cell_slice.load_uint(4)
        if tag not in (0, 1):
            raise ConfigError(f'WorkchainFormat deserialization error: unexpected tag {tag}')
        if v:
            return cls(
                type_='wfmt_basic',
                vm_version=cell_slice.load_int(32),
                vm_mode=cell_slice.load_uint(64)
            )
        min_addr_len = cell_slice.load_uint(12)
        max_addr_len = cell_slice.load_uint(12)
        addr_len_step = cell_slice.load_uint(12)
        workchain_type_id = cell_slice.load_uint(32)
        assert min_addr_len >= 64
        assert min_addr_len <= max_addr_len
        assert max_addr_len <= 1023
        assert addr_len_step <= 1023
        assert workchain_type_id >= 1
        return cls(
            type_='wfmt_ext',
            min_addr_len=min_addr_len,
            max_addr_len=max_addr_len,
            addr_len_step=addr_len_step,
            workchain_type_id=workchain_type_id
        )


class WcSplitMergeTimings(TlbScheme):
    """
    wc_split_merge_timings#0
    split_merge_delay:uint32 split_merge_interval:uint32
    min_split_merge_interval:uint32 max_split_merge_delay:uint32
    = WcSplitMergeTimings;
    """

    def __init__(self,
                 split_merge_delay: int,
                 split_merge_interval: int,
                 min_split_merge_interval: int,
                 max_split_merge_delay: int,
                 ):
        self.split_merge_delay = split_merge_delay
        self.split_merge_interval = split_merge_interval
        self.min_split_merge_interval = min_split_merge_interval
        self.max_split_merge_delay = max_split_merge_delay

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_uint(4)
        if tag != 0:
            raise ConfigError(f'WorkchainFormat deserialization error: unexpected tag {tag}')
        return cls(
            split_merge_delay=cell_slice.load_uint(32),
            split_merge_interval=cell_slice.load_uint(32),
            min_split_merge_interval=cell_slice.load_uint(32),
            max_split_merge_delay=cell_slice.load_uint(32)
        )


class WorkchainDescr(TlbScheme):
    """
    workchain#a6 enabled_since:uint32 actual_min_split:(## 8)
    min_split:(## 8) max_split:(## 8) { actual_min_split <= min_split }
    basic:(## 1) active:Bool accept_msgs:Bool flags:(## 13) { flags = 0 }
    zerostate_root_hash:bits256 zerostate_file_hash:bits256
    version:uint32 format:(WorkchainFormat basic)
    = WorkchainDescr;

    workchain_v2#a7 enabled_since:uint32 actual_min_split:(## 8)
    min_split:(## 8) max_split:(## 8) { actual_min_split <= min_split }
    basic:(## 1) active:Bool accept_msgs:Bool flags:(## 13) { flags = 0 }
    zerostate_root_hash:bits256 zerostate_file_hash:bits256
    version:uint32 format:(WorkchainFormat basic)
    split_merge_timings:WcSplitMergeTimings
    = WorkchainDescr;
    """

    def __init__(self,
                 type_: typing.Literal["workchain", "workchain_v2"],
                 enabled_since: int,
                 actual_min_split: int,
                 min_split: int,
                 max_split: int,
                 basic: int,
                 active: bool,
                 accept_msgs: bool,
                 flags: int,
                 zerostate_root_hash: bytes,
                 zerostate_file_hash: bytes,
                 version: int,
                 format: WorkchainFormat,
                 split_merge_timings: typing.Optional[WcSplitMergeTimings] = None
                 ):
        self.type_ = type_
        self.enabled_since = enabled_since
        self.actual_min_split = actual_min_split
        self.min_split = min_split
        self.max_split = max_split
        self.basic = basic
        self.active = active
        self.accept_msgs = accept_msgs
        self.flags = flags
        self.zerostate_root_hash = zerostate_root_hash
        self.zerostate_file_hash = zerostate_file_hash
        self.version = version
        self.format = format
        self.split_merge_timings = split_merge_timings

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_bytes(1)[:1]
        if tag not in (b'\xa6', b'\xa7'):
            raise ConfigError(f'WorkchainDescr deserialization error: unexpected tag {tag}')
        enabled_since = cell_slice.load_uint(32)
        actual_min_split = cell_slice.load_uint(8)
        min_split = cell_slice.load_uint(8)
        max_split = cell_slice.load_uint(8)
        assert actual_min_split <= min_split
        basic = cell_slice.load_bit()
        active = cell_slice.load_bool()
        accept_msgs = cell_slice.load_bool()
        flags = cell_slice.load_uint(13)
        assert flags == 0
        zerostate_root_hash = cell_slice.load_bytes(32)
        zerostate_file_hash = cell_slice.load_bytes(32)
        version = cell_slice.load_uint(32)
        format = WorkchainFormat.deserialize(cell_slice, basic)
        type_ = 'workchain' if tag == b'\xa6' else 'workchain_v2'
        split_merge_timings = WcSplitMergeTimings.deserialize(cell_slice) if type_ == 'workchain_v2' else None
        return cls(
            type_=type_,
            enabled_since=enabled_since,
            actual_min_split=actual_min_split,
            min_split=min_split,
            max_split=max_split,
            basic=basic,
            active=active,
            accept_msgs=accept_msgs,
            flags=flags,
            zerostate_root_hash=zerostate_root_hash,
            zerostate_file_hash=zerostate_file_hash,
            version=version,
            format=format,
            split_merge_timings=split_merge_timings,
        )


class ConfigParam12(TlbScheme):
    """
    _ workchains:(HashmapE 32 WorkchainDescr) = ConfigParam 12;
    """
    def __init__(self, workchains: typing.Dict[int, WorkchainDescr]):
        self.workchains = workchains

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(
            workchains=cell_slice.load_dict(32, value_deserializer=WorkchainDescr.deserialize)
        )


class ComplaintPricing(TlbScheme):
    """
    complaint_prices#1a deposit:Grams bit_price:Grams cell_price:Grams = ComplaintPricing;
    """
    def __init__(self,
                 deposit: int,
                 bit_price: int,
                 cell_price: int,
                 ):
        self.deposit = deposit
        self.bit_price = bit_price
        self.cell_price = cell_price

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_bytes(1)[:1]
        if tag != b'\x1a':
            raise ConfigError(f'ComplaintPricing deserialization error: unexpected prefix tag {tag}')
        return cls(
            deposit=cell_slice.load_coins(),
            bit_price=cell_slice.load_coins(),
            cell_price=cell_slice.load_coins()
        )


class ConfigParam13(ComplaintPricing):
    """
    _ ComplaintPricing = ConfigParam 13;
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return super().deserialize(cell_slice)


class BlockCreateFees(TlbScheme):
    """
    block_grams_created#6b masterchain_block_fee:Grams basechain_block_fee:Grams
    = BlockCreateFees;
    """
    def __init__(self,
                 masterchain_block_fee: int,
                 basechain_block_fee: int,
                 ):
        self.masterchain_block_fee = masterchain_block_fee
        self.basechain_block_fee = basechain_block_fee

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_bytes(1)[:1]
        if tag != b'\x6b':
            raise ConfigError(f'BlockCreateFees deserialization error: unexpected prefix tag {tag}')
        return cls(
            masterchain_block_fee=cell_slice.load_coins(),
            basechain_block_fee=cell_slice.load_coins(),
        )


class ConfigParam14(BlockCreateFees):
    """
    _ BlockCreateFees = ConfigParam 14;
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return super().deserialize(cell_slice)


class ConfigParam15(TlbScheme):
    """
    _ validators_elected_for:uint32 elections_start_before:uint32
      elections_end_before:uint32 stake_held_for:uint32
      = ConfigParam 15;
    """
    def __init__(self,
                 validators_elected_for: int,
                 elections_start_before: int,
                 elections_end_before: int,
                 stake_held_for: int,
                 ):
        self.validators_elected_for = validators_elected_for
        self.elections_start_before = elections_start_before
        self.elections_end_before = elections_end_before
        self.stake_held_for = stake_held_for

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(
            validators_elected_for=cell_slice.load_uint(32),
            elections_start_before=cell_slice.load_uint(32),
            elections_end_before=cell_slice.load_uint(32),
            stake_held_for=cell_slice.load_uint(32)
        )


class ConfigParam16(TlbScheme):
    """
    _ max_validators:(## 16) max_main_validators:(## 16) min_validators:(## 16)
      { max_validators >= max_main_validators }
      { max_main_validators >= min_validators }
      { min_validators >= 1 }
      = ConfigParam 16;
    """
    def __init__(self,
                 max_validators: int,
                 max_main_validators: int,
                 min_validators: int,
                 ):
        self.max_validators = max_validators
        self.max_main_validators = max_main_validators
        self.min_validators = min_validators

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        max_validators = cell_slice.load_uint(16)
        max_main_validators = cell_slice.load_uint(16)
        min_validators = cell_slice.load_uint(16)
        assert max_validators >= max_main_validators
        assert max_main_validators >= min_validators
        assert min_validators >= 1
        return cls(
            max_validators=max_validators,
            max_main_validators=max_main_validators,
            min_validators=min_validators
        )


class ConfigParam17(TlbScheme):
    """
    _ min_stake:Grams max_stake:Grams min_total_stake:Grams max_stake_factor:uint32 = ConfigParam 17;
    """
    def __init__(self,
                 min_stake: int,
                 max_stake: int,
                 min_total_stake: int,
                 max_stake_factor: int
                 ):
        self.min_stake = min_stake
        self.max_stake = max_stake
        self.min_total_stake = min_total_stake
        self.max_stake_factor = max_stake_factor

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(
            min_stake=cell_slice.load_coins(),
            max_stake=cell_slice.load_coins(),
            min_total_stake=cell_slice.load_coins(),
            max_stake_factor=cell_slice.load_uint(32)
        )


class StoragePrices(TlbScheme):
    """
    _#cc utime_since:uint32 bit_price_ps:uint64 cell_price_ps:uint64
    mc_bit_price_ps:uint64 mc_cell_price_ps:uint64 = StoragePrices;
    """
    def __init__(self,
                 utime_since: int,
                 bit_price_ps: int,
                 cell_price_ps: int,
                 mc_bit_price_ps: int,
                 mc_cell_price_ps: int,
                 ):
        self.utime_since = utime_since
        self.bit_price_ps = bit_price_ps
        self.cell_price_ps = cell_price_ps
        self.mc_bit_price_ps = mc_bit_price_ps
        self.mc_cell_price_ps = mc_cell_price_ps

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_bytes(1)[:1]
        if tag != b'\xcc':
            raise ConfigError(f'StoragePrices deserialization error: unexpected prefix tag: {tag}')
        return cls(
            utime_since=cell_slice.load_uint(32),
            bit_price_ps=cell_slice.load_uint(64),
            cell_price_ps=cell_slice.load_uint(64),
            mc_bit_price_ps=cell_slice.load_uint(64),
            mc_cell_price_ps=cell_slice.load_uint(64)
        )


class ConfigParam18(TlbScheme):
    """
    _ (Hashmap 32 StoragePrices) = ConfigParam 18;
    """

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice) -> typing.Dict[int, StoragePrices]:
        return cell_slice.load_hashmap(32, value_deserializer=StoragePrices.deserialize)


class GasLimitsPrices(TlbScheme):
    """
    gas_prices#dd gas_price:uint64 gas_limit:uint64 gas_credit:uint64
    block_gas_limit:uint64 freeze_due_limit:uint64 delete_due_limit:uint64
    = GasLimitsPrices;

    gas_prices_ext#de gas_price:uint64 gas_limit:uint64 special_gas_limit:uint64 gas_credit:uint64
    block_gas_limit:uint64 freeze_due_limit:uint64 delete_due_limit:uint64
    = GasLimitsPrices;

    gas_flat_pfx#d1 flat_gas_limit:uint64 flat_gas_price:uint64 other:GasLimitsPrices
    = GasLimitsPrices;
    """
    def __init__(self,
                 type_: typing.Literal["gas_prices", "gas_prices_ext", "gas_flat_pfx"],
                 gas_price: typing.Optional[int] = None,
                 gas_limit: typing.Optional[int] = None,
                 gas_credit: typing.Optional[int] = None,
                 block_gas_limit: typing.Optional[int] = None,
                 freeze_due_limit: typing.Optional[int] = None,
                 delete_due_limit: typing.Optional[int] = None,
                 special_gas_limit: typing.Optional[int] = None,
                 flat_gas_limit: typing.Optional[int] = None,
                 flat_gas_price: typing.Optional[int] = None,
                 other: typing.Optional["GasLimitsPrices"] = None
                 ):
        self.type_ = type_
        self.gas_price = gas_price
        self.gas_limit = gas_limit
        self.gas_credit = gas_credit
        self.block_gas_limit = block_gas_limit
        self.freeze_due_limit = freeze_due_limit
        self.delete_due_limit = delete_due_limit
        self.special_gas_limit = special_gas_limit
        self.flat_gas_limit = flat_gas_limit
        self.flat_gas_price = flat_gas_price
        self.other = other

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_bytes(1)[:1]
        if tag in (b'\xdd', b'\xde'):
            gas_price = cell_slice.load_uint(64)
            gas_limit = cell_slice.load_uint(64)
            type_ = 'gas_prices'
            special_gas_limit = None
            if tag == b'\xde':
                type_ = 'gas_prices_ext'
                special_gas_limit = cell_slice.load_uint(64)
            gas_credit = cell_slice.load_uint(64)
            block_gas_limit = cell_slice.load_uint(64)
            freeze_due_limit = cell_slice.load_uint(64)
            delete_due_limit = cell_slice.load_uint(64)
            return cls(
                type_=type_,
                gas_price=gas_price,
                gas_limit=gas_limit,
                gas_credit=gas_credit,
                special_gas_limit=special_gas_limit,
                block_gas_limit=block_gas_limit,
                freeze_due_limit=freeze_due_limit,
                delete_due_limit=delete_due_limit
            )
        elif tag == b'\xd1':
            return cls(
                type_='gas_flat_pfx',
                flat_gas_limit=cell_slice.load_uint(64),
                flat_gas_price=cell_slice.load_uint(64),
                other=cls.deserialize(cell_slice)
            )
        raise ConfigError(f'GasLimitsPrices deserialization error: unknown prefix tag: {tag}')


class ConfigParam20(GasLimitsPrices):
    """
    config_mc_gas_prices#_ GasLimitsPrices = ConfigParam 20;
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return super().deserialize(cell_slice)


class ConfigParam21(GasLimitsPrices):
    """
    config_gas_prices#_ GasLimitsPrices = ConfigParam 21;
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return super().deserialize(cell_slice)


class ParamLimits(TlbScheme):
    """
    param_limits#c3 underload:# soft_limit:# { underload <= soft_limit }
    hard_limit:# { soft_limit <= hard_limit } = ParamLimits;
    """
    def __init__(self,
                 underload: int,
                 soft_limit: int,
                 hard_limit: int,
                 ):
        self.underload = underload
        self.soft_limit = soft_limit
        self.hard_limit = hard_limit

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_bytes(1)[:1]
        if tag != b'\xc3':
            raise ConfigError(f'ParamLimits deserialization error: unexpected tag {tag}')
        underload = cell_slice.load_uint(32)
        soft_limit = cell_slice.load_uint(32)
        assert underload <= soft_limit
        hard_limit = cell_slice.load_uint(32)
        assert soft_limit <= hard_limit
        return cls(
            underload=underload,
            soft_limit=soft_limit,
            hard_limit=hard_limit
        )


class BlockLimits(TlbScheme):
    """
    block_limits#5d bytes:ParamLimits gas:ParamLimits lt_delta:ParamLimits
    = BlockLimits;
    """
    def __init__(self,
                 bytes: ParamLimits,
                 gas: ParamLimits,
                 lt_delta: ParamLimits):
        self.bytes = bytes
        self.gas = gas
        self.lt_delta = lt_delta

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_bytes(1)[:1]
        if tag != b'\x5d':
            raise ConfigError(f'BlockLimits deserialization error: unexpected tag {tag}')
        return cls(
            bytes=ParamLimits.deserialize(cell_slice),
            gas=ParamLimits.deserialize(cell_slice),
            lt_delta=ParamLimits.deserialize(cell_slice),
        )


class ConfigParam22(BlockLimits):
    """
    config_mc_block_limits#_ BlockLimits = ConfigParam 22;
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return super().deserialize(cell_slice)


class ConfigParam23(BlockLimits):
    """
    config_block_limits#_ BlockLimits = ConfigParam 23;
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return super().deserialize(cell_slice)


class MsgForwardPrices(TlbScheme):
    """
    msg_forward_prices#ea lump_price:uint64 bit_price:uint64 cell_price:uint64
    ihr_price_factor:uint32 first_frac:uint16 next_frac:uint16 = MsgForwardPrices;
    """
    def __init__(self,
                 lump_price: int,
                 bit_price: int,
                 cell_price: int,
                 ihr_price_factor: int,
                 first_frac: int,
                 next_frac: int
                 ):
        self.lump_price = lump_price
        self.bit_price = bit_price
        self.cell_price = cell_price
        self.ihr_price_factor = ihr_price_factor
        self.first_frac = first_frac
        self.next_frac = next_frac

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_bytes(1)[:1]
        if tag != b'\xea':
            raise ConfigError(f'ParamLimits deserialization error: unexpected tag {tag}')
        return cls(
            lump_price=cell_slice.load_uint(64),
            bit_price=cell_slice.load_uint(64),
            cell_price=cell_slice.load_uint(64),
            ihr_price_factor=cell_slice.load_uint(32),
            first_frac=cell_slice.load_uint(16),
            next_frac=cell_slice.load_uint(16),
        )


class ConfigParam24(MsgForwardPrices):
    """
    // used for messages to/from masterchain
    config_mc_fwd_prices#_ MsgForwardPrices = ConfigParam 24;
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return super().deserialize(cell_slice)


class ConfigParam25(MsgForwardPrices):
    """
    // used for all other messages
    config_fwd_prices#_ MsgForwardPrices = ConfigParam 25;
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return super().deserialize(cell_slice)


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


class ConsensusConfig(TlbScheme):
    """
    consensus_config#d6 round_candidates:# { round_candidates >= 1 }
    next_candidate_delay_ms:uint32 consensus_timeout_ms:uint32
    fast_attempts:uint32 attempt_duration:uint32 catchain_max_deps:uint32
    max_block_bytes:uint32 max_collated_bytes:uint32 = ConsensusConfig;

    consensus_config_new#d7 flags:(## 7) { flags = 0 } new_catchain_ids:Bool
    round_candidates:(## 8) { round_candidates >= 1 }
    next_candidate_delay_ms:uint32 consensus_timeout_ms:uint32
    fast_attempts:uint32 attempt_duration:uint32 catchain_max_deps:uint32
    max_block_bytes:uint32 max_collated_bytes:uint32 = ConsensusConfig;

    consensus_config_v3#d8 flags:(## 7) { flags = 0 } new_catchain_ids:Bool
    round_candidates:(## 8) { round_candidates >= 1 }
    next_candidate_delay_ms:uint32 consensus_timeout_ms:uint32
    fast_attempts:uint32 attempt_duration:uint32 catchain_max_deps:uint32
    max_block_bytes:uint32 max_collated_bytes:uint32
    proto_version:uint16 = ConsensusConfig;

    consensus_config_v4#d9 flags:(## 7) { flags = 0 } new_catchain_ids:Bool
    round_candidates:(## 8) { round_candidates >= 1 }
    next_candidate_delay_ms:uint32 consensus_timeout_ms:uint32
    fast_attempts:uint32 attempt_duration:uint32 catchain_max_deps:uint32
    max_block_bytes:uint32 max_collated_bytes:uint32
    proto_version:uint16 catchain_max_blocks_coeff:uint32 = ConsensusConfig;
    """

    def __init__(self, type_: typing.Literal["consensus_config", "consensus_config_new", "consensus_config_v3", "consensus_config_v4"],
                 round_candidates: typing.Optional[int] = None,
                 next_candidate_delay_ms: typing.Optional[int] = None,
                 consensus_timeout_ms: typing.Optional[int] = None,
                 fast_attempts: typing.Optional[int] = None,
                 attempt_duration: typing.Optional[int] = None,
                 catchain_max_deps: typing.Optional[int] = None,
                 max_block_bytes: typing.Optional[int] = None,
                 max_collated_bytes: typing.Optional[int] = None,
                 flags: typing.Optional[int] = None,
                 new_catchain_ids: typing.Optional[int] = None,
                 proto_version: typing.Optional[int] = None,
                 catchain_max_blocks_coeff: typing.Optional[int] = None,
                 ):
        self.type_ = type_
        self.round_candidates = round_candidates
        self.next_candidate_delay_ms = next_candidate_delay_ms
        self.consensus_timeout_ms = consensus_timeout_ms
        self.fast_attempts = fast_attempts
        self.attempt_duration = attempt_duration
        self.catchain_max_deps = catchain_max_deps
        self.max_block_bytes = max_block_bytes
        self.max_collated_bytes = max_collated_bytes
        self.flags = flags
        self.new_catchain_ids = new_catchain_ids
        self.proto_version = proto_version
        self.catchain_max_blocks_coeff = catchain_max_blocks_coeff

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_bytes(1)[:1]
        types = {
            b'\xd6': 'consensus_config',
            b'\xd7': 'consensus_config_new',
            b'\xd8': 'consensus_config_v3',
            b'\xd9': 'consensus_config_v4',
        }
        if tag not in types:
            raise ConfigError(f'ConsensusConfig deserialization error: unexpected tag {tag}')
        type_ = types.get(tag)
        flags = None
        new_catchain_ids = None
        if type_ != 'consensus_config':
            flags = cell_slice.load_uint(7)
            assert flags == 0
            new_catchain_ids = cell_slice.load_bool()
            round_candidates = cell_slice.load_uint(8)
        else:
            round_candidates = cell_slice.load_uint(32)
        assert round_candidates >= 1
        next_candidate_delay_ms = cell_slice.load_uint(32)
        consensus_timeout_ms = cell_slice.load_uint(32)
        fast_attempts = cell_slice.load_uint(32)
        attempt_duration = cell_slice.load_uint(32)
        catchain_max_deps = cell_slice.load_uint(32)
        max_block_bytes = cell_slice.load_uint(32)
        max_collated_bytes = cell_slice.load_uint(32)
        proto_version = None
        catchain_max_blocks_coeff = None
        if type_ in ('consensus_config_v3', 'consensus_config_v4'):
            proto_version = cell_slice.load_uint(16)
        if type_ == 'consensus_config_v4':
            catchain_max_blocks_coeff = cell_slice.load_uint(32)
        return cls(
            type_=type_,
            flags=flags,
            new_catchain_ids=new_catchain_ids,
            round_candidates=round_candidates,
            next_candidate_delay_ms=next_candidate_delay_ms,
            consensus_timeout_ms=consensus_timeout_ms,
            fast_attempts=fast_attempts,
            attempt_duration=attempt_duration,
            catchain_max_deps=catchain_max_deps,
            max_block_bytes=max_block_bytes,
            max_collated_bytes=max_collated_bytes,
            proto_version=proto_version,
            catchain_max_blocks_coeff=catchain_max_blocks_coeff,
        )


class ConfigParam29(ConsensusConfig):
    """
    _ ConsensusConfig = ConfigParam 29;
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return super().deserialize(cell_slice)


class ConfigParam31(TlbScheme):
    """
    _ fundamental_smc_addr:(HashmapE 256 True) = ConfigParam 31;
    """

    def __init__(self, fundamental_smc_addr: dict):
        self.fundamental_smc_addr = fundamental_smc_addr

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(fundamental_smc_addr=cell_slice.load_dict(256, value_deserializer=lambda src: True))


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


class ConfigParam32(TlbScheme):
    """
    _ prev_validators:ValidatorSet = ConfigParam 32;
    """

    def __init__(self, prev_validators: "ValidatorSet"):
        self.prev_validators = prev_validators

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(prev_validators=ValidatorSet.deserialize(cell_slice))


class ConfigParam33(TlbScheme):
    """
    _ prev_temp_validators:ValidatorSet = ConfigParam 33;
    """

    def __init__(self, prev_temp_validators: "ValidatorSet"):
        self.prev_temp_validators = prev_temp_validators

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(prev_temp_validators=ValidatorSet.deserialize(cell_slice))


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

class ConfigParam35(TlbScheme):
    """
    _ cur_temp_validators:ValidatorSet = ConfigParam 35;
    """

    def __init__(self, cur_temp_validators: "ValidatorSet"):
        self.cur_temp_validators = cur_temp_validators

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(cur_temp_validators=ValidatorSet.deserialize(cell_slice))


class ConfigParam36(TlbScheme):
    """
    _ next_validators:ValidatorSet = ConfigParam 36;
    """

    def __init__(self, next_validators: "ValidatorSet"):
        self.next_validators = next_validators

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(next_validators=ValidatorSet.deserialize(cell_slice))


class ConfigParam37(TlbScheme):
    """
    _ next_temp_validators:ValidatorSet = ConfigParam 37;
    """

    def __init__(self, next_temp_validators: "ValidatorSet"):
        self.next_temp_validators = next_temp_validators

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(next_temp_validators=ValidatorSet.deserialize(cell_slice))


class SuspendedAddressList(TlbScheme):
    """
    suspended_address_list#00 addresses:(HashmapE 288 Unit) suspended_until:uint32 = SuspendedAddressList;
    """
    def __init__(self,
                 addresses: dict,
                 suspended_until: int
                 ):
        self.addresses = addresses
        self.suspended_until = suspended_until

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_bytes(1)[:1]
        if tag != b'\x00':
            raise ConfigError(f'SuspendedAddressList deserialization error: unexpected prefix tag {tag}')
        return cls(
            addresses=cell_slice.load_dict(288, value_deserializer=lambda src: None),
            suspended_until=cell_slice.load_uint(32)
        )


class ConfigParam44(SuspendedAddressList):
    """
    _ SuspendedAddressList = ConfigParam 44;
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return super().deserialize(cell_slice)


class OracleBridgeParams(TlbScheme):
    """
    oracle_bridge_params#_ bridge_address:bits256 oracle_mutlisig_address:bits256 oracles:(HashmapE 256 uint256) external_chain_address:bits256 = OracleBridgeParams;
    """
    def __init__(self,
                 bridge_address: bytes,
                 oracle_mutlisig_address: bytes,
                 oracles: dict,
                 external_chain_address: bytes
                 ):
        self.bridge_address = bridge_address
        self.bridge_address_hex = bridge_address.hex()
        self.oracle_mutlisig_address = oracle_mutlisig_address
        self.oracle_mutlisig_address_hex = oracle_mutlisig_address.hex()
        self.oracles = oracles
        self.external_chain_address_hex = external_chain_address.hex()

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(
            bridge_address=cell_slice.load_bytes(32),
            oracle_mutlisig_address=cell_slice.load_bytes(32),
            oracles=cell_slice.load_dict(256, value_deserializer=lambda src: src.load_uint(256)),
            external_chain_address=cell_slice.load_bytes(32)
        )


class ConfigParam71(OracleBridgeParams):
    """
    _ OracleBridgeParams = ConfigParam 71; // Ethereum bridge
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return super().deserialize(cell_slice)


class ConfigParam72(OracleBridgeParams):
    """
    _ OracleBridgeParams = ConfigParam 72; // Binance Smart Chain bridge
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return super().deserialize(cell_slice)


class ConfigParam73(OracleBridgeParams):
    """
    _ OracleBridgeParams = ConfigParam 73; // Polygon bridge
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return super().deserialize(cell_slice)


class JettonBridgePrices(TlbScheme):
    """
    // Note that chains in which bridge, minter and jetton-wallet operate are fixated
    jetton_bridge_prices#_ bridge_burn_fee:Coins bridge_mint_fee:Coins
                           wallet_min_tons_for_storage:Coins
                           wallet_gas_consumption:Coins
                           minter_min_tons_for_storage:Coins
                           discover_gas_consumption:Coins = JettonBridgePrices;
    """
    def __init__(self,
                 bridge_burn_fee: int,
                 bridge_mint_fee: int,
                 wallet_min_tons_for_storage: int,
                 wallet_gas_consumption: int,
                 minter_min_tons_for_storage: int,
                 discover_gas_consumption: int,
                 ):
        self.bridge_burn_fee = bridge_burn_fee
        self.bridge_mint_fee = bridge_mint_fee
        self.wallet_min_tons_for_storage = wallet_min_tons_for_storage
        self.wallet_gas_consumption = wallet_gas_consumption
        self.minter_min_tons_for_storage = minter_min_tons_for_storage
        self.discover_gas_consumption = discover_gas_consumption

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(
            bridge_burn_fee=cell_slice.load_coins(),
            bridge_mint_fee=cell_slice.load_coins(),
            wallet_min_tons_for_storage=cell_slice.load_coins(),
            wallet_gas_consumption=cell_slice.load_coins(),
            minter_min_tons_for_storage=cell_slice.load_coins(),
            discover_gas_consumption=cell_slice.load_coins(),
        )


class JettonBridgeParams(TlbScheme):
    """
    jetton_bridge_params_v0#00 bridge_address:bits256 oracles_address:bits256 oracles:(HashmapE 256 uint256) state_flags:uint8 burn_bridge_fee:Coins = JettonBridgeParams;
    jetton_bridge_params_v1#01 bridge_address:bits256 oracles_address:bits256 oracles:(HashmapE 256 uint256) state_flags:uint8 prices:^JettonBridgePrices external_chain_address:bits256 = JettonBridgeParams;
    """
    def __init__(self,
                 type_: typing.Literal["jetton_bridge_params_v0", "jetton_bridge_params_v1"],
                 bridge_address: bytes,
                 oracles_address: bytes,
                 oracles: dict,
                 state_flags: int,
                 burn_bridge_fee: typing.Optional[int] = None,
                 prices: typing.Optional[JettonBridgePrices] = None,
                 external_chain_address: typing.Optional[bytes] = None,

                 ):
        self.bridge_address = bridge_address
        self.bridge_address_hex = bridge_address.hex()
        self.oracles_address = oracles_address
        self.oracles_address_hex = oracles_address.hex()
        self.oracles = oracles
        self.state_flags = state_flags
        self.burn_bridge_fee = burn_bridge_fee
        self.prices = prices
        self.external_chain_address = external_chain_address
        if external_chain_address:
            self.external_chain_address_hex = external_chain_address.hex()

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_bytes(1)[:1]
        if tag not in (b'\x00', b'\x01'):
            raise ConfigError(f'JettonBridgeParams deserialization error: unexpected prefix tag {tag}')
        bridge_address = cell_slice.load_bytes(32)
        oracles_address = cell_slice.load_bytes(32)
        oracles = cell_slice.load_dict(256, value_deserializer=lambda src: src.load_uint(256))
        state_flags = cell_slice.load_uint(8)
        burn_bridge_fee = None
        prices = None
        if tag == b'\x00':
            type_ = 'jetton_bridge_params_v0'
            burn_bridge_fee = cell_slice.load_coins()
        else:
            type_ = 'jetton_bridge_params_v1'
            prices = JettonBridgePrices.deserialize(cell_slice.load_ref().begin_parse())
        return cls(
            type_=type_,
            bridge_address=bridge_address,
            oracles_address=oracles_address,
            oracles=oracles,
            state_flags=state_flags,
            burn_bridge_fee=burn_bridge_fee,
            prices=prices
        )


class ConfigParam79(JettonBridgeParams):
    """
    _ JettonBridgeParams = ConfigParam 79; // ETH->TON token bridge
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return super().deserialize(cell_slice)


class ConfigParam81(JettonBridgeParams):
    """
    _ JettonBridgeParams = ConfigParam 81; // BNB->TON token bridge
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return super().deserialize(cell_slice)


class ConfigParam82(JettonBridgeParams):
    """
    _ JettonBridgeParams = ConfigParam 82; // Polygon->TON token bridge
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return super().deserialize(cell_slice)


class ConfigParam(TlbScheme):

    params = {
        0: ConfigParam0,
        1: ConfigParam1,
        2: ConfigParam2,
        3: ConfigParam3,
        4: ConfigParam4,
        5: ConfigParam5,
        6: ConfigParam6,
        7: ConfigParam7,
        8: ConfigParam8,
        9: ConfigParam9,
        10: ConfigParam10,
        11: ConfigParam11,
        12: ConfigParam12,
        13: ConfigParam13,
        14: ConfigParam14,
        15: ConfigParam15,
        16: ConfigParam16,
        17: ConfigParam17,
        18: ConfigParam18,
        20: ConfigParam20,
        21: ConfigParam21,
        22: ConfigParam22,
        23: ConfigParam23,
        24: ConfigParam24,
        25: ConfigParam25,
        28: ConfigParam28,
        29: ConfigParam29,
        31: ConfigParam31,
        32: ConfigParam32,
        33: ConfigParam33,
        34: ConfigParam34,
        35: ConfigParam35,
        36: ConfigParam36,
        37: ConfigParam37,
        44: ConfigParam44,
        71: ConfigParam71,
        72: ConfigParam72,
        73: ConfigParam73,
        79: ConfigParam79,
        81: ConfigParam81,
        82: ConfigParam82
    }

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, *args):
        pass

