import typing

from .tlb import TlbScheme, TlbError
from .account import ShardAccount, AccountBlock
from .utils import MerkleUpdate, deserialize_shard_hashes
from ..boc import Slice, Cell, Builder
from ..boc.dict.dict import HashMap


# TODO provide in each constructor already deserialized args, not slice


class BlockError(TlbError):
    pass


class Block(TlbScheme):
    """
    block#11ef55aa global_id:int32
    info:^BlockInfo value_flow:^ValueFlow
    state_update:^(MERKLE_UPDATE ShardState)
    extra:^BlockExtra = Block;
    """
    def __init__(self, global_id: int, info: "BlockInfo", value_flow: "ValueFlow", state_update: MerkleUpdate, extra: "BlockExtra"):
        self.global_id = global_id
        self.info = info
        self.value_flow = value_flow
        self.state_update = state_update
        self.extra = extra

    @classmethod
    def serialize(cls, *args): ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_bytes(4)
        if tag != b'\x11\xefU\xaa':
            raise BlockError(f'Block deserialization error: unknown prefix tag: {tag}')

        global_id = cell_slice.load_int(32)
        info = BlockInfo.deserialize(cell_slice.load_ref().begin_parse())
        value_flow = ValueFlow.deserialize(cell_slice.load_ref().begin_parse())
        state_update = MerkleUpdate.deserialize(cell_slice.load_ref(), ShardState.deserialize)
        extra = BlockExtra.deserialize(cell_slice.load_ref().begin_parse())

        return cls(global_id, info, value_flow, state_update, extra)


class BlockInfo(TlbScheme):
    """
    block_info#9bc7a987 version:uint32 not_master:(## 1) after_merge:(## 1) before_split:(## 1)  after_split:(## 1)
    want_split:Bool want_merge:Bool key_block:Bool vert_seqno_incr:(## 1) flags:(## 8) { flags <= 1 }
    seq_no:# vert_seq_no:# { vert_seq_no >= vert_seqno_incr } { prev_seq_no:# } { ~prev_seq_no + 1 = seq_no }
    shard:ShardIdent gen_utime:uint32 start_lt:uint64 end_lt:uint64
    gen_validator_list_hash_short:uint32 gen_catchain_seqno:uint32
    min_ref_mc_seqno:uint32 prev_key_block_seqno:uint32
    gen_software:flags . 0?GlobalVersion master_ref:not_master?^BlkMasterInfo prev_ref:^(BlkPrevInfo after_merge)
    prev_vert_ref:vert_seqno_incr?^(BlkPrevInfo 0) = BlockInfo;
    """
    def __init__(self, cell_slice: Slice):
        self.version = cell_slice.load_uint(32)
        self.not_master = cell_slice.load_bit()
        self.after_merge = cell_slice.load_bit()
        self.before_split = cell_slice.load_bit()
        self.after_split = cell_slice.load_bit()
        self.want_split = cell_slice.load_bool()
        self.want_merge = cell_slice.load_bool()
        self.key_block = cell_slice.load_bool()
        self.vert_seqno_incr = cell_slice.load_bit()
        self.flags = cell_slice.load_uint(8)
        if not (self.flags <= 1):
            raise BlockError(f'deserialization error: flags = {self.flags} > 1')
        self.seqno = cell_slice.load_uint(32)
        self.vert_seqno = cell_slice.load_uint(32)
        if not (self.vert_seqno >= self.vert_seqno_incr):
            raise BlockError(f'deserialization error: vert_seqno = {self.vert_seqno} < vert_seqno_incr = {self.vert_seqno_incr}')
        self.shard = ShardIdent.deserialize(cell_slice)
        self.gen_utime = cell_slice.load_uint(32)
        self.start_lt = cell_slice.load_uint(64)
        self.end_lt = cell_slice.load_uint(64)
        self.gen_validator_list_hash_short = cell_slice.load_uint(32)
        self.gen_catchain_seqno = cell_slice.load_uint(32)
        self.min_ref_mc_seqno = cell_slice.load_uint(32)
        self.prev_key_block_seqno = cell_slice.load_uint(32)
        self.gen_software = None
        self.master_ref = None
        if bin(self.flags)[-1] == '1':
            self.gen_software = GlobalVersion.deserialize(cell_slice)
        if self.not_master:
            self.master_ref = BlkMasterInfo.deserialize(cell_slice.load_ref().begin_parse())
        self.prev_ref = BlkPrevInfo.deserialize(cell_slice.load_ref().begin_parse(), self.after_merge)
        self.prev_vert_ref = None
        if self.vert_seqno_incr:
            self.prev_vert_ref = BlkPrevInfo.deserialize(cell_slice.load_ref().begin_parse(), 0)

    @classmethod
    def serialize(cls, *args): ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        if cell_slice.is_special():
            return None
        tag = cell_slice.load_bytes(4)
        if tag != b'\x9b\xc7\xa9\x87':
            raise BlockError(f'BlockInfo deserialization error unknown prefix tag: {tag}')
        return cls(cell_slice)


class ShardIdent(TlbScheme):
    """
    shard_ident$00 shard_pfx_bits:(#<= 60) workchain_id:int32 shard_prefix:uint64 = ShardIdent;
    """

    def __init__(self, cell_slice: Slice):
        self.shard_pfx_bits = cell_slice.load_uint(int(60).bit_length())
        self.workchain_id = cell_slice.load_int(32)
        self.shard_prefix = cell_slice.load_uint(64)

    @classmethod
    def serialize(cls, *args): ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_bits(2).to01()
        if tag != '00':
            raise BlockError(f'ShardIdent deserialization error: unknown prefix: {tag}')
        return cls(cell_slice)


class GlobalVersion(TlbScheme):
    """
    capabilities#c4 version:uint32 capabilities:uint64 = GlobalVersion;
    """

    def __init__(self, version: int, capabilities: int):
        self.version = version
        self.capabilities = capabilities

    @classmethod
    def serialize(cls, *args): ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_bytes(1)
        if tag[:1] != b'\xc4':
            raise BlockError(f'GlobalVersion deserialization error: unknown prefix: {tag}')
        return cls(version=cell_slice.load_int(32), capabilities=cell_slice.load_uint(64))


class BlkMasterInfo(TlbScheme):
    """
    master_info$_ master:ExtBlkRef = BlkMasterInfo;
    """

    def __init__(self, master: "ExtBlkRef"):
        self.master = master

    @classmethod
    def serialize(cls, *args): ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(ExtBlkRef.deserialize(cell_slice))


class BlkPrevInfo(TlbScheme):
    """
    prev_blk_info$_ prev:ExtBlkRef = BlkPrevInfo 0;
    prev_blks_info$_ prev1:^ExtBlkRef prev2:^ExtBlkRef = BlkPrevInfo 1;
    """

    def __init__(self, type_: str, **kwargs):
        self.type_ = type_
        for k, v in kwargs.items():
            setattr(self, k, v)

    @classmethod
    def serialize(cls, *args): ...

    @classmethod
    def deserialize(cls, cell_slice: Slice, after_merge: int):
        kwargs = {}
        if not after_merge:
            type_ = 'prev_blk_info'
            kwargs['prev'] = ExtBlkRef.deserialize(cell_slice)
        else:
            type_ = 'prev_blks_info'
            kwargs['prev1'] = ExtBlkRef.deserialize(cell_slice.load_ref().begin_parse())
            kwargs['prev2'] = ExtBlkRef.deserialize(cell_slice.load_ref().begin_parse())

        return cls(type_, **kwargs)


class ExtBlkRef(TlbScheme):
    """
    ext_blk_ref$_ end_lt:uint64
    seq_no:uint32 root_hash:bits256 file_hash:bits256 = ExtBlkRef;
    """

    def __init__(self, cell_slice: Slice):
        self.end_lt = cell_slice.load_int(64)
        self.seqno = cell_slice.load_uint(32)
        self.root_hash = cell_slice.load_bytes(32)
        self.file_hash = cell_slice.load_bytes(32)

    @classmethod
    def serialize(cls, *args): ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(cell_slice)


class ValueFlow(TlbScheme):
    """
    value_flow#b8e48dfb
    ^[
        from_prev_blk:CurrencyCollection
        to_next_blk:CurrencyCollection
        imported:CurrencyCollection
        exported:CurrencyCollection
    ]
    fees_collected:CurrencyCollection
    ^[
        fees_imported:CurrencyCollection
        recovered:CurrencyCollection
        created:CurrencyCollection
        minted:CurrencyCollection
    ] = ValueFlow;

    value_flow_v2#3ebf98b7
    ^[ from_prev_blk:CurrencyCollection
        to_next_blk:CurrencyCollection
        imported:CurrencyCollection
        exported:CurrencyCollection ]
        fees_collected:CurrencyCollection
        burned:CurrencyCollection
    ^[
        fees_imported:CurrencyCollection
        recovered:CurrencyCollection
        created:CurrencyCollection
        minted:CurrencyCollection
    ] = ValueFlow;
    """

    def __init__(self, type_, **kwargs):
        self.type_ = type_
        for k, v in kwargs.items():
            setattr(self, k, v)

    @classmethod
    def serialize(cls, *args): ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        if cell_slice.is_special():
            return None
        kwargs = {}
        tag = cell_slice.load_bytes(4)
        if tag == b'\xb8\xe4\x8d\xfb':
            type_ = 'value_flow'
            ref1 = cell_slice.load_ref().begin_parse()
            ref2 = cell_slice.load_ref().begin_parse()
            kwargs['from_prev_blk'], kwargs['to_next_blk'], kwargs['imported'], kwargs['exported'] = [CurrencyCollection.deserialize(ref1) for _ in range(4)]
            kwargs['fees_collected'] = CurrencyCollection.deserialize(cell_slice)
            kwargs['fees_imported'], kwargs['recovered'], kwargs['created'], kwargs['minted'] = [CurrencyCollection.deserialize(ref2) for _ in range(4)]
        elif tag == b'>\xbf\x98\xb7':
            type_ = 'value_flow_v2'
            ref1 = cell_slice.load_ref().begin_parse()
            ref2 = cell_slice.load_ref().begin_parse()
            kwargs['from_prev_blk'], kwargs['to_next_blk'], kwargs['imported'], kwargs['exported'] = [CurrencyCollection.deserialize(ref1) for _ in range(4)]
            kwargs['fees_collected'] = CurrencyCollection.deserialize(cell_slice)
            kwargs['burned'] = CurrencyCollection.deserialize(cell_slice)
            kwargs['fees_imported'], kwargs['recovered'], kwargs['created'], kwargs['minted'] = [CurrencyCollection.deserialize(ref2) for _ in range(4)]
        else:
            raise BlockError(f'ValueFlow deserialization error unknown prefix tag: {tag}')
        return cls(type_, **kwargs)


class CurrencyCollection(TlbScheme):
    """
    currencies$_ grams:Grams other:ExtraCurrencyCollection = CurrencyCollection;
    """

    def __init__(self, grams: int, other: "ExtraCurrencyCollection" = None) -> None:
        self.grams = grams
        if other is None:
            other = ExtraCurrencyCollection({})
        self.other = other

    def serialize(self):
        return Builder().store_coins(self.grams).store_cell(self.other.serialize()).end_cell()

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        grams = cell_slice.load_coins()
        other = ExtraCurrencyCollection.deserialize(cell_slice)
        return cls(grams, other)

    def __repr__(self):
        return f"{{'grams': {self.grams}, 'other': {self.other.dict}}}"


class ExtraCurrencyCollection(TlbScheme):
    """
    extra_currencies$_ dict:(HashmapE 32 (VarUInteger 32)) = ExtraCurrencyCollection
    """

    def __init__(self, dict_: dict):
        self.dict = dict_

    def serialize(self) -> Cell:
        dict_cell = HashMap(32, value_serializer=lambda src, dest: dest.store_uint(src, 32)).serialize()
        return Builder().store_dict(dict_cell).end_cell()

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        def value_deserializer(src):
            return src.load_var_uint(5)
        dict_ = cell_slice.load_dict(32, value_deserializer=value_deserializer)
        return cls(dict_)


class ShardState(TlbScheme):
    """
    _ ShardStateUnsplit = ShardState;
    split_state#5f327da5 left:^ShardStateUnsplit right:^ShardStateUnsplit = ShardState;
    """

    def __init__(self, type_: str, **kwargs):
        self.type_ = type_
        for k, v in kwargs.items():
            setattr(self, k, v)

    @classmethod
    def serialize(cls, *args): ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.preload_bytes(4)
        if tag == b'_2}\xa5':
            cell_slice.load_bytes(4)
            return cls(type_='split_state',
                       left=ShardStateUnsplit.deserialize(cell_slice.load_ref().begin_parse()),
                       right=ShardStateUnsplit.deserialize(cell_slice.load_ref().begin_parse())
                       )
        return cls(type_='_', shard_state_unsplit=ShardStateUnsplit.deserialize(cell_slice))


class ShardStateUnsplit(TlbScheme):
    """
    shard_state#9023afe2 global_id:int32 shard_id:ShardIdent seq_no:uint32 vert_seq_no:#
    gen_utime:uint32 gen_lt:uint64 min_ref_mc_seqno:uint32 out_msg_queue_info:^OutMsgQueueInfo
    before_split:(## 1) accounts:^ShardAccounts
    ^[ overload_history:uint64 underload_history:uint64
        total_balance:CurrencyCollection
        total_validator_fees:CurrencyCollection
        libraries:(HashmapE 256 LibDescr)
        master_ref:(Maybe BlkMasterInfo)
    ] custom:(Maybe ^McStateExtra)
    = ShardStateUnsplit;
    """

    def __init__(self,
                 global_id: int,
                 shard_id: ShardIdent,
                 seq_no: int,
                 vert_seq_no: int,
                 gen_utime: int,
                 gen_lt: int,
                 min_ref_mc_seqno: int,
                 out_msg_queue_info: Cell,
                 before_split: int,
                 accounts: "ShardAccounts",
                 overload_history: int,
                 underload_history: int,
                 total_balance: CurrencyCollection,
                 total_validator_fees: CurrencyCollection,
                 libraries: dict,
                 master_ref: typing.Optional[BlkMasterInfo],
                 custom: typing.Optional["McStateExtra"],
                 ):
        self.global_id = global_id
        self.shard_id = shard_id
        self.seq_no = seq_no
        self.vert_seq_no = vert_seq_no
        self.gen_utime = gen_utime
        self.gen_lt = gen_lt
        self.min_ref_mc_seqno = min_ref_mc_seqno
        self.out_msg_queue_info = out_msg_queue_info
        self.before_split = before_split
        self.accounts = accounts
        self.overload_history = overload_history
        self.underload_history = underload_history
        self.total_balance = total_balance
        self.total_validator_fees = total_validator_fees
        self.libraries = libraries
        self.master_ref = master_ref
        self.custom = custom

    @classmethod
    def serialize(cls, *args): ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        if cell_slice.is_special():
            return None
        tag = cell_slice.load_bytes(4)
        if not tag == b'\x90#\xaf\xe2':
            raise BlockError(f'ShardStateUnsplit deserialization error unknown prefix tag: {tag}')

        global_id = cell_slice.load_int(32)
        shard_id = ShardIdent.deserialize(cell_slice)
        seq_no = cell_slice.load_uint(32)
        vert_seq_no = cell_slice.load_uint(32)
        gen_utime = cell_slice.load_uint(32)
        gen_lt = cell_slice.load_uint(64)
        min_ref_mc_seqno = cell_slice.load_uint(32)
        out_msg_queue_info = cell_slice.load_ref()  # TODO
        before_split = cell_slice.load_bit()
        # accounts = cell_slice.load_ref()
        accounts = ShardAccounts.deserialize(cell_slice.load_ref().begin_parse())
        ref = cell_slice.load_ref().begin_parse()
        overload_history = None
        underload_history = None
        total_balance = None
        total_validator_fees = None
        libraries = None
        master_ref = None
        if not ref.is_special():
            overload_history = ref.load_uint(64)
            underload_history = ref.load_uint(64)
            total_balance = CurrencyCollection.deserialize(ref)
            # print(total_balance, ref)
            total_validator_fees = CurrencyCollection.deserialize(ref)
            libraries = ref.load_dict(256)
            master_ref = BlkMasterInfo.deserialize(ref) if ref.load_bit() else None
        custom = McStateExtra.deserialize(cell_slice.load_ref().begin_parse()) if cell_slice.load_bit() else None

        return cls(global_id, shard_id, seq_no, vert_seq_no, gen_utime,
                   gen_lt, min_ref_mc_seqno, out_msg_queue_info, before_split, accounts,
                   overload_history, underload_history, total_balance, total_validator_fees,
                   libraries, master_ref, custom)


class ShardAccounts(TlbScheme):
    """
    _ (HashmapAugE 256 ShardAccount DepthBalanceInfo) = ShardAccounts;
    """
    def serialize(self, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cell_slice.load_hashmap_aug_e(key_length=256,
                                             x_deserializer=ShardAccount.deserialize,
                                             y_deserializer=DepthBalanceInfo.deserialize)


class OutMsgQueueInfo(TlbScheme):
    """
    _ out_queue:OutMsgQueue proc_info:ProcessedInfo
    ihr_pending:IhrPendingInfo = OutMsgQueueInfo;
    """
    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, *args):
        pass


class OutMsgQueue(TlbScheme):
    """
    _ (HashmapAugE 352 EnqueuedMsg uint64) = OutMsgQueue;
    """
    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, *args):
        pass


class DepthBalanceInfo(TlbScheme):
    """
    depth_balance$_ split_depth:(#<= 30) balance:CurrencyCollection = DepthBalanceInfo;
    """

    def __init__(self, split_depth: int, balance: CurrencyCollection):
        self.split_depth = split_depth
        self.balance = balance

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(cell_slice.load_uint(5),  # (#<= 30)
                   CurrencyCollection.deserialize(cell_slice))


class McStateExtra(TlbScheme):
    """
    masterchain_state_extra#cc26 shard_hashes:ShardHashes config:ConfigParams
    ^[ flags:(## 16) { flags <= 1 }
        validator_info:ValidatorInfo
        prev_blocks:OldMcBlocksInfo
        after_key_block:Bool
        last_key_block:(Maybe ExtBlkRef)
        block_create_stats:(flags . 0)?BlockCreateStats
    ]
    global_balance:CurrencyCollection
    = McStateExtra;
    """

    def __init__(self,
                 shard_hashes: dict,
                 config: "ConfigParams",
                 flags: int,
                 validator_info: "ValidatorInfo",
                 prev_blocks: "OldMcBlocksInfo",
                 after_key_block: bool,
                 last_key_block: typing.Optional[ExtBlkRef],
                 block_create_stats: typing.Optional["BlockCreateStats"],
                 global_balance: CurrencyCollection
                 ):
        self.shard_hashes = shard_hashes
        self.config = config
        self.flags = flags
        self.validator_info = validator_info
        self.prev_blocks = prev_blocks
        self.after_key_block = after_key_block
        self.last_key_block = last_key_block
        self.block_create_stats = block_create_stats
        self.global_balance = global_balance

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        if cell_slice.is_special():
            return None
        tag = cell_slice.load_bytes(2)
        if tag != b'\xcc&':
            raise BlockError(f'McStateExtra deserialization error unknown prefix tag: {tag}')
        shard_hashes = deserialize_shard_hashes(cell_slice)
        config = ConfigParams.deserialize(cell_slice)
        ref = cell_slice.load_ref().begin_parse()
        flags = ref.load_uint(16)
        if not (flags <= 1):
            raise BlockError(f'McStateExtra deserialization error expected flags <= 1, got: {flags}')
        validator_info = ValidatorInfo.deserialize(ref)
        prev_blocks = OldMcBlocksInfo.deserialize(ref)
        after_key_block = ref.load_bool()
        ref.load_bits(65)  # TODO why ?
        last_key_block = ExtBlkRef.deserialize(ref) if ref.load_bit() else None
        block_create_stats = None
        if bin(flags)[-1] == '1':
            block_create_stats = BlockCreateStats.deserialize(ref)
        global_balance = CurrencyCollection.deserialize(cell_slice)
        return cls(shard_hashes, config, flags, validator_info, prev_blocks, after_key_block, last_key_block, block_create_stats, global_balance)


class McBlockExtra(TlbScheme):
    """
    masterchain_block_extra#cca5
    key_block:(## 1)
    shard_hashes:ShardHashes
    shard_fees:ShardFees
    ^[
        prev_blk_signatures:(HashmapE 16 CryptoSignaturePair)
        recover_create_msg:(Maybe ^InMsg)
        mint_msg:(Maybe ^InMsg)
        ]
    config: key_block?ConfigParams
    """

    def __init__(self,
                 key_block: int,
                 shard_hashes: dict,
                 shard_fees: Cell,
                 prev_blk_signatures: dict,
                 recover_create_msg: typing.Optional[Cell],
                 mint_msg: typing.Optional[Cell],
                 config: typing.Optional["ConfigParams"]
                 ):
        self.key_block = key_block
        self.shard_hashes = shard_hashes
        self.shard_fees = shard_fees
        self.prev_blk_signatures = prev_blk_signatures
        self.recover_create_msg = recover_create_msg
        self.mint_msg = mint_msg
        self.config = config

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        if cell_slice.is_special():
            return None
        tag = cell_slice.load_bytes(2)
        if tag != b'\xcc\xa5':
            raise BlockError(f'McBlockExtra deserialization error unknown prefix tag: {tag}')
        key_block = cell_slice.load_bit()
        shard_hashes = deserialize_shard_hashes(cell_slice)
        shard_fees = cell_slice.load_maybe_ref()
        ref = cell_slice.load_ref().begin_parse()
        prev_blk_signatures = ref.load_dict(16)
        recover_create_msg = ref.load_maybe_ref()
        mint_msg = ref.load_maybe_ref()
        config = None
        if key_block:
            config = ConfigParams.deserialize(cell_slice)

        return cls(key_block, shard_hashes, shard_fees, prev_blk_signatures, recover_create_msg, mint_msg, config)


class ConfigParams(TlbScheme):
    """
    _ config_addr:bits256 config:^(Hashmap 32 ^Cell) = ConfigParams;
    """

    def __init__(self, config_addr: str, config: dict):
        self.config_addr = config_addr
        self.config = config

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(config_addr=cell_slice.load_bytes(32).hex(), config=cell_slice.load_ref().begin_parse().load_hashmap(32, value_deserializer=lambda src: src.load_ref().begin_parse()))


class ValidatorInfo(TlbScheme):
    """
    validator_info$_
    validator_list_hash_short:uint32
    catchain_seqno:uint32
    nx_cc_updated:Bool = ValidatorInfo;
    """

    def __init__(self, validator_list_hash_short: int, catchain_seqno: int, nx_cc_updated: bool):
        self.validator_list_hash_short = validator_list_hash_short
        self.catchain_seqno = catchain_seqno
        self.nx_cc_updated = nx_cc_updated

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(
            validator_list_hash_short=cell_slice.load_uint(32),
            catchain_seqno=cell_slice.load_uint(32),
            nx_cc_updated=cell_slice.load_bool()
        )


class OldMcBlocksInfo(TlbScheme):
    """
    _ (HashmapAugE 32 KeyExtBlkRef KeyMaxLt) = OldMcBlocksInfo;
    """

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cell_slice.load_hashmap_aug_e(32, KeyExtBlkRef.deserialize, KeyMaxLt.deserialize)


class KeyExtBlkRef(TlbScheme):
    """
    _ key:Bool blk_ref:ExtBlkRef = KeyExtBlkRef;
    """

    def __init__(self, key: bool, blk_ref: ExtBlkRef):
        self.key = key
        self.blk_ref = blk_ref

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(cell_slice.load_bool(), ExtBlkRef.deserialize(cell_slice))


class KeyMaxLt(TlbScheme):
    """
    _ key:Bool max_end_lt:uint64 = KeyMaxLt;
    """

    def __init__(self, key: bool, max_end_lt: int):
        self.key = key
        self.max_end_lt = max_end_lt

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(cell_slice.load_bool(), cell_slice.load_uint(64))


class BlockCreateStats(TlbScheme):
    """
    block_create_stats#17 counters:(HashmapE 256 CreatorStats) = BlockCreateStats;
    block_create_stats_ext#34 counters:(HashmapAugE 256 CreatorStats uint32) = BlockCreateStats;
    """

    def __init__(self, type_: str, counters: dict):
        self.type_ = type_
        self.counters = counters

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_bytes(1)
        if tag[:1] == b'\x17':
            type_ = 'block_create_stats'
            return cls(type_, cell_slice.load_dict(256, value_deserializer=CreatorStats.deserialize))
        if tag[:1] == b'\x34':
            type_ = 'block_create_stats_ext'

            def y_deserializer(src):
                return src.load_uint(32)
            return cls(type_, cell_slice.load_hashmap_aug_e(256, x_deserializer=CreatorStats.deserialize, y_deserializer=y_deserializer))
        else:
            raise BlockError(f'BlockCreateStats deserialization error tag: {tag}')



class CreatorStats(TlbScheme):
    """
    creator_info#4 mc_blocks:Counters shard_blocks:Counters = CreatorStats;
    """

    def __init__(self, mc_blocks: "Counters", shard_blocks: "Counters"):
        self.mc_blocks = mc_blocks
        self.shard_blocks = shard_blocks

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_uint(4)
        if tag != 4:
            raise BlockError(f'CreatorStats deserialization error tag: {tag}')
        return cls(Counters.deserialize(cell_slice), Counters.deserialize(cell_slice))


class Counters(TlbScheme):
    """
    counters#_ last_updated:uint32 total:uint64 cnt2048:uint64 cnt65536:uint64 = Counters;
    """

    def __init__(self, last_updated: int, total: int, cnt2048: int, cnt65536: int):
        self.last_updated = last_updated
        self.total = total
        self.cnt2048 = cnt2048
        self.cnt65536 = cnt65536

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(cell_slice.load_uint(32), cell_slice.load_uint(64), cell_slice.load_uint(64), cell_slice.load_uint(64))


class BlockExtra(TlbScheme):
    """
    block_extra in_msg_descr:^InMsgDescr
    out_msg_descr:^OutMsgDescr
    account_blocks:^ShardAccountBlocks
    rand_seed:bits256
    created_by:bits256
    custom:(Maybe ^McBlockExtra) = BlockExtra;
    """

    def __init__(self,
                 in_msg_descr: typing.Tuple[dict, list],
                 out_msg_descr: typing.Tuple[dict, list],
                 account_blocks: typing.Tuple[dict, list],
                 rand_seed: bytes,
                 created_by: bytes,
                 custom: typing.Optional[McBlockExtra]):
        self.in_msg_descr = in_msg_descr
        self.out_msg_descr = out_msg_descr
        self.account_blocks = account_blocks
        self.rand_seed = rand_seed
        self.created_by = created_by
        self.custom = custom

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        from .transaction import InMsg, OutMsg, ImportFees
        if cell_slice.is_special():
            return None
        tag = cell_slice.load_bytes(4)
        if tag != b'J3\xf6\xfd':
            raise BlockError(f'BlockExtra deserialization error tag: {tag}')
        in_msg_descr = cell_slice.load_ref().begin_parse().load_hashmap_aug_e(256, x_deserializer=InMsg.deserialize, y_deserializer=ImportFees.deserialize)
        out_msg_descr = cell_slice.load_ref().begin_parse().load_hashmap_aug_e(256, x_deserializer=OutMsg.deserialize, y_deserializer=CurrencyCollection.deserialize)
        account_blocks = cell_slice.load_ref().begin_parse().load_hashmap_aug_e(256, x_deserializer=AccountBlock.deserialize, y_deserializer=CurrencyCollection.deserialize)
        rand_seed = cell_slice.load_bytes(32)
        created_by = cell_slice.load_bytes(32)
        custom = McBlockExtra.deserialize(cell_slice.load_ref().begin_parse()) if cell_slice.load_bit() else None
        return cls(in_msg_descr, out_msg_descr, account_blocks, rand_seed, created_by, custom)


class BinTree(TlbScheme):
    """
    bt_leaf$0 {X:Type} leaf:X = BinTree X;
    bt_fork$1 {X:Type} left:^(BinTree X) right:^(BinTree X)
    = BinTree X;
    """
    def __init__(self, list_: list):
        self.list = list_

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        if cell_slice.load_bit():
            return cls(cls.deserialize(cell_slice.load_ref().begin_parse()).list + cls.deserialize(cell_slice.load_ref().begin_parse()).list)
        else:
            return cls([cell_slice])


class ShardDescr(TlbScheme):
    """
    shard_descr#b seq_no:uint32 reg_mc_seqno:uint32
    start_lt:uint64 end_lt:uint64
    root_hash:bits256 file_hash:bits256
    before_split:Bool before_merge:Bool
    want_split:Bool want_merge:Bool
    nx_cc_updated:Bool flags:(## 3) { flags = 0 }
    next_catchain_seqno:uint32 next_validator_shard:uint64
    min_ref_mc_seqno:uint32 gen_utime:uint32
    split_merge_at:FutureSplitMerge
    fees_collected:CurrencyCollection
    funds_created:CurrencyCollection = ShardDescr;

    shard_descr_new#a seq_no:uint32 reg_mc_seqno:uint32
    start_lt:uint64 end_lt:uint64
    root_hash:bits256 file_hash:bits256
    before_split:Bool before_merge:Bool
    want_split:Bool want_merge:Bool
    nx_cc_updated:Bool flags:(## 3) { flags = 0 }
    next_catchain_seqno:uint32 next_validator_shard:uint64
    min_ref_mc_seqno:uint32 gen_utime:uint32
    split_merge_at:FutureSplitMerge
    ^[
        fees_collected:CurrencyCollection
        funds_created:CurrencyCollection
    ] = ShardDescr;
    """

    def __init__(self, seq_no: int, reg_mc_seqno: int, start_lt: int, end_lt: int, root_hash: bytes, file_hash: bytes,
                 before_split: bool, before_merge: bool, want_split: bool, want_merge: bool, nx_cc_updated: bool,
                 flags: int, next_catchain_seqno: int, next_validator_shard: int, min_ref_mc_seqno: int,
                 gen_utime: int, split_merge_at: "FutureSplitMerge", fees_collected: CurrencyCollection, funds_created: CurrencyCollection):
        self.seq_no = seq_no
        self.reg_mc_seqno = reg_mc_seqno
        self.start_lt = start_lt
        self.end_lt = end_lt
        self.root_hash = root_hash
        self.file_hash = file_hash
        self.before_split = before_split
        self.before_merge = before_merge
        self.want_split = want_split
        self.want_merge = want_merge
        self.nx_cc_updated = nx_cc_updated
        self.flags = flags
        self.next_catchain_seqno = next_catchain_seqno
        self.next_validator_shard = next_validator_shard
        self.min_ref_mc_seqno = min_ref_mc_seqno
        self.gen_utime = gen_utime
        self.split_merge_at = split_merge_at
        self.fees_collected = fees_collected
        self.funds_created = funds_created

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_bits(4).to01()
        if tag not in ('1011', '1010'):  # b and a
            raise BlockError(f'ShardDescr deserialization error unknown prefix tag: {tag}')

        seq_no = cell_slice.load_uint(32)
        reg_mc_seqno = cell_slice.load_uint(32)
        start_lt = cell_slice.load_uint(64)
        end_lt = cell_slice.load_uint(64)
        root_hash = cell_slice.load_bytes(32)
        file_hash = cell_slice.load_bytes(32)
        before_split = cell_slice.load_bool()
        before_merge = cell_slice.load_bool()
        want_split = cell_slice.load_bool()
        want_merge = cell_slice.load_bool()
        nx_cc_updated = cell_slice.load_bool()
        flags = cell_slice.load_uint(3)
        if flags != 0:
            raise BlockError(f'ShardDescr deserialization error flags expected to be zero, got: {flags}')
        next_catchain_seqno = cell_slice.load_uint(32)
        next_validator_shard = cell_slice.load_uint(64)
        min_ref_mc_seqno = cell_slice.load_uint(32)
        gen_utime = cell_slice.load_uint(32)
        split_merge_at = FutureSplitMerge.deserialize(cell_slice)

        if tag == '1011':  # b
            fees_collected = CurrencyCollection.deserialize(cell_slice)
            funds_created = CurrencyCollection.deserialize(cell_slice)
        else:  # a
            ref = cell_slice.load_ref().begin_parse()
            fees_collected = CurrencyCollection.deserialize(ref)
            funds_created = CurrencyCollection.deserialize(ref)
        return cls(seq_no, reg_mc_seqno, start_lt, end_lt, root_hash, file_hash,
                   before_split, before_merge, want_split, want_merge, nx_cc_updated,
                   flags, next_catchain_seqno, next_validator_shard, min_ref_mc_seqno,
                   gen_utime, split_merge_at, fees_collected, funds_created)


class FutureSplitMerge(TlbScheme):
    """
    fsm_none$0 = FutureSplitMerge;
    fsm_split$10 split_utime:uint32 interval:uint32 = FutureSplitMerge;
    fsm_merge$11 merge_utime:uint32 interval:uint32 = FutureSplitMerge;
    """

    def __init__(self, type_, **kwargs):
        self.type_ = type_
        for k, v in kwargs.items():
            setattr(self, k, v)

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice) -> typing.Optional["FutureSplitMerge"]:
        if not cell_slice.load_bit():  # 0
            return None
        if not cell_slice.load_bit():  # 10
            return cls('fsm_split', split_utime=cell_slice.load_uint(32), interval=cell_slice.load_uint(32))
        return cls('fsm_merge', merge_utime=cell_slice.load_uint(32), interval=cell_slice.load_uint(32))  # 11
