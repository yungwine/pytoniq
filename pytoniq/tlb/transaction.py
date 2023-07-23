import typing

from .block import CurrencyCollection
from .tlb import TlbScheme, TlbError
from .account import AccountStatus, StateInit, StorageUsedShort
from .utils import HashUpdate
from ..boc import Slice, Builder, Cell
from ..boc.address import Address


class TransactionError(TlbError):
    pass


class Transaction(TlbScheme):
    """
    transaction$0111 account_addr:bits256 lt:uint64
    prev_trans_hash:bits256 prev_trans_lt:uint64 now:uint32
    outmsg_cnt:uint15
    orig_status:AccountStatus end_status:AccountStatus
    ^[
        in_msg:(Maybe ^(Message Any))
        out_msgs:(HashmapE 15 ^(Message Any))
    ]
    total_fees:CurrencyCollection state_update:^(HASH_UPDATE Account)
    description:^TransactionDescr = Transaction;

    """

    def __init__(self,
                 account_addr: bytes,
                 lt: int,
                 prev_trans_hash: bytes,
                 prev_trans_lt: int,
                 now: int,
                 outmsg_cnt: int,
                 orig_status: AccountStatus,
                 end_status: AccountStatus,
                 in_msg: typing.Optional["MessageAny"],
                 out_msgs: typing.List["MessageAny"],
                 total_fees: CurrencyCollection,
                 state_update: HashUpdate,
                 description: "TransactionDescr"
                 ):
        self.account_addr = account_addr.hex()
        self.lt = lt
        self.prev_trans_hash = prev_trans_hash
        self.prev_trans_lt = prev_trans_lt
        self.now = now
        self.outmsg_cnt = outmsg_cnt
        self.orig_status = orig_status
        self.end_status = end_status
        self.in_msg = in_msg
        self.out_msgs = out_msgs
        self.total_fees = total_fees
        self.state_update = state_update
        self.description: TransactionOrdinary = description
        # the type hinting above is wrong, but it was made for better experience in IDE cause most time you work with ordinary trs

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        if cell_slice.is_special():
            return cell_slice.to_cell()
        tag = cell_slice.load_bits(4).to01()
        if tag != '0111':
            raise TransactionError(f'Transaction deserialization error unknown prefix tag: {tag}')
        account_addr = cell_slice.load_bytes(32)
        lt = cell_slice.load_uint(64)
        prev_trans_hash = cell_slice.load_bytes(32)
        prev_trans_lt = cell_slice.load_uint(64)
        now = cell_slice.load_uint(32)
        outmsg_cnt = cell_slice.load_uint(15)
        orig_status = AccountStatus.deserialize(cell_slice)
        end_status = AccountStatus.deserialize(cell_slice)
        ref = cell_slice.load_ref().begin_parse()
        in_msg = None
        if ref.load_bit():
            in_msg = MessageAny.deserialize(ref.load_ref().begin_parse())
        out_msgs = ref.load_dict(15, value_deserializer=lambda src: MessageAny.deserialize(src.load_ref().begin_parse()))
        if out_msgs is not None:
            out_msgs = [out_msgs[i] for i in sorted(out_msgs)]
        total_fees = CurrencyCollection.deserialize(cell_slice)
        state_update = HashUpdate.deserialize(cell_slice.load_ref().begin_parse())
        description = TransactionDescr.deserialize(cell_slice.load_ref().begin_parse())

        return cls(account_addr, lt, prev_trans_hash, prev_trans_lt, now, outmsg_cnt, orig_status, end_status, in_msg, out_msgs, total_fees, state_update, description)


""" ########## MESSAGES ########## """


class MessageAny(TlbScheme):
    """
    message$_ {X:Type} info:CommonMsgInfo
    init:(Maybe (Either StateInit ^StateInit))
    body:(Either X ^X) = Message X;
    """
    def __init__(self, info: typing.Union["InternalMsgInfo", "ExternalMsgInfo", "ExternalOutMsgInfo"],
                 init: typing.Optional[StateInit], body: Cell):
        self.info = info
        self.init = init
        self.body = body

    def serialize(self) -> Cell:
        builder = Builder().store_cell(self.info.serialize())
        if self.init:
            builder.store_bit(1)  # maybe true
            builder.store_bit(1)  # Either right
            builder.store_ref(self.init.serialize())
        else:
            builder.store_bit(0)  # maybe false
        builder.store_maybe_ref(self.body)  # Either right
        return builder.end_cell()

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        info = CommonMsgInfo.deserialize(cell_slice)
        init = None
        maybe = cell_slice.load_bit()
        if maybe:
            either = cell_slice.load_bit()
            if either:  # right
                init = StateInit.deserialize(cell_slice.load_ref().begin_parse())
            else:  # left
                init = StateInit.deserialize(cell_slice)
        either = cell_slice.load_bit()
        if either:  # right
            body = cell_slice.load_ref()
        else:  # left
            body = cell_slice.to_cell()
        return cls(info, init, body)


class CommonMsgInfo(TlbScheme):
    """
    int_msg_info$0 ihr_disabled:Bool bounce:Bool bounced:Bool
    src:MsgAddressInt dest:MsgAddressInt
    value:CurrencyCollection ihr_fee:Grams fwd_fee:Grams
    created_lt:uint64 created_at:uint32 = CommonMsgInfo;

    ext_in_msg_info$10 src:MsgAddressExt dest:MsgAddressInt
    import_fee:Grams = CommonMsgInfo;

    ext_out_msg_info$11 src:MsgAddressInt dest:MsgAddressExt
    created_lt:uint64 created_at:uint32 = CommonMsgInfo;
    """
    def __init__(self):
        pass

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.preload_bit()
        if not tag:  # 0
            return InternalMsgInfo.deserialize(cell_slice)
        tag = cell_slice.preload_bits(2).to01()
        if tag == '10':
            return ExternalMsgInfo.deserialize(cell_slice)
        # 11
        return ExternalOutMsgInfo.deserialize(cell_slice)


class InternalMsgInfo(CommonMsgInfo):
    """
    int_msg_info$0 ihr_disabled:Bool bounce:Bool bounced:Bool
    src:MsgAddressInt dest:MsgAddressInt
    value:CurrencyCollection ihr_fee:Grams fwd_fee:Grams
    created_lt:uint64 created_at:uint32 = CommonMsgInfo;
    """
    def __init__(self, ihr_disabled: bool, bounce: bool, bounced: bool, src: Address, dest: Address,
                 value: CurrencyCollection, ihr_fee: int, fwd_fee: int, created_lt: int, created_at: int):
        super().__init__()
        self.ihr_disabled = ihr_disabled
        self.bounce = bounce
        self.bounced = bounced
        self.src = src
        self.dest = dest
        self.value = value
        self.value_coins: int = value.grams
        self.ihr_fee = ihr_fee
        self.fwd_fee = fwd_fee
        self.created_lt = created_lt
        self.created_at = created_at

    def serialize(self) -> Cell:
        builder = Builder()
        builder.store_uint(0, 1)  # $0
        return builder\
            .store_bool(self.ihr_disabled)\
            .store_bool(self.bounce)\
            .store_bool(self.bounced)\
            .store_address(self.src)\
            .store_address(self.dest)\
            .store_cell(self.value.serialize())\
            .store_coins(self.ihr_fee)\
            .store_coins(self.fwd_fee)\
            .store_uint(self.created_lt, 64)\
            .store_uint(self.created_at, 32)\
            .end_cell()

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_bit()
        if tag:
            raise TransactionError(f'InternalMsgInfo deserialization error unknown prefix tag: {tag}')
        return cls(
            ihr_disabled=cell_slice.load_bool(),
            bounce=cell_slice.load_bool(),
            bounced=cell_slice.load_bool(),
            src=cell_slice.load_address(),
            dest=cell_slice.load_address(),
            value=CurrencyCollection.deserialize(cell_slice),
            ihr_fee=cell_slice.load_coins(),
            fwd_fee=cell_slice.load_coins(),
            created_lt=cell_slice.load_uint(64),
            created_at=cell_slice.load_uint(32)
        )


class ExternalMsgInfo(CommonMsgInfo):
    """
    ext_in_msg_info$10 src:MsgAddressExt dest:MsgAddressInt
    import_fee:Grams = CommonMsgInfo;
    """
    def __init__(self, src: Address, dest: Address, import_fee: int):
        super().__init__()
        self.src = src
        self.dest = dest
        self.import_fee = import_fee

    def serialize(self) -> Cell:
        builder = Builder()
        builder.store_uint(2, 2)  # $10
        return builder\
            .store_address(self.src)\
            .store_address(self.dest)\
            .store_coins(self.import_fee)\
            .end_cell()

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_bits(2).to01()
        if tag != '10':
            raise TransactionError(f'ExternalMsgInfo deserialization error unknown prefix tag: {tag}')
        return cls(
            src=cell_slice.load_address(),
            dest=cell_slice.load_address(),
            import_fee=cell_slice.load_coins()
        )


class ExternalOutMsgInfo(CommonMsgInfo):
    """
    ext_out_msg_info$11 src:MsgAddressInt dest:MsgAddressExt
    created_lt:uint64 created_at:uint32 = CommonMsgInfo;
    """
    def __init__(self, src: Address, dest: Address, created_lt: int, created_at: int):
        super().__init__()
        self.src = src
        self.dest = dest
        self.created_lt = created_lt
        self.created_at = created_at

    def serialize(self) -> Cell:
        builder = Builder()
        builder.store_uint(3, 2)  # $11
        return builder\
            .store_address(self.src)\
            .store_address(self.dest)\
            .store_uint(self.created_lt, 64)\
            .store_uint(self.created_at, 32)\
            .end_cell()

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_bits(2).to01()
        if tag != '11':
            raise TransactionError(f'ExternalOutMsgInfo deserialization error unknown prefix tag: {tag}')
        return cls(
            src=cell_slice.load_address(),
            dest=cell_slice.load_address(),
            created_lt=cell_slice.load_uint(64),
            created_at=cell_slice.load_uint(32)
        )


""" ########## PHASES ########## """


class AccStatusChange(TlbScheme):
    """
    acst_unchanged$0 = AccStatusChange;  // x -> x
    acst_frozen$10 = AccStatusChange;    // init -> frozen
    acst_deleted$11 = AccStatusChange;   // frozen -> deleted
    """
    def __init__(self, type_: typing.Literal["unchanged", "frozen", "deleted"]):
        self.type_ = type_

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_bit()
        if not tag:
            return cls('unchanged')
        tag = cell_slice.load_bit()
        if not tag:
            return cls('frozen')
        return cls('deleted')


class ComputeSkipReason(TlbScheme):
    """
    cskip_no_state$00 = ComputeSkipReason;
    cskip_bad_state$01 = ComputeSkipReason;
    cskip_no_gas$10 = ComputeSkipReason;
    cskip_suspended$110 = ComputeSkipReason;
    """
    def __init__(self, type_: typing.Literal["no_state", "bad_state", "no_gas", "suspended"]):
        self.type_ = type_

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_bit()
        if not tag:
            tag = cell_slice.load_bit()
            if not tag:  # 00
                return cls('no_state')
            # 01
            return cls('bad_state')
        tag = cell_slice.load_bit()
        if not tag:  # 10
            return cls('no_gas')
        tag = cell_slice.load_bit()
        if not tag:  # 110
            return cls('suspended')
        raise TransactionError(f'ComputeSkipReason deserialization error unknown prefix tag: {111}')


class TrStoragePhase(TlbScheme):
    """
    tr_phase_storage$_ storage_fees_collected:Grams
    storage_fees_due:(Maybe Grams)
    status_change:AccStatusChange
    = TrStoragePhase;
    """
    def __init__(self,
                 storage_fees_collected: int,
                 storage_fees_due: typing.Optional[int],
                 status_change: AccStatusChange
                 ):
        self.storage_fees_collected = storage_fees_collected
        self.storage_fees_due = storage_fees_due
        self.status_change = status_change

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(
            storage_fees_collected=cell_slice.load_coins(),
            storage_fees_due=cell_slice.load_coins() if cell_slice.load_bit() else None,
            status_change=AccStatusChange.deserialize(cell_slice)
        )


class TrCreditPhase(TlbScheme):
    """
    tr_phase_credit$_ due_fees_collected:(Maybe Grams)
    credit:CurrencyCollection = TrCreditPhase;
    """
    def __init__(self,
                 due_fees_collected: typing.Optional[int],
                 credit: CurrencyCollection,
                 ):
        self.due_fees_collected = due_fees_collected
        self.credit = credit

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(
            due_fees_collected=cell_slice.load_coins() if cell_slice.load_bit() else None,
            credit=CurrencyCollection.deserialize(cell_slice),
        )


class TrComputePhase(TlbScheme):
    """
    tr_phase_compute_skipped$0 reason:ComputeSkipReason = TrComputePhase;

    tr_phase_compute_vm$1 success:Bool msg_state_used:Bool
    account_activated:Bool gas_fees:Grams
    ^[
        gas_used:(VarUInteger 7)
        gas_limit:(VarUInteger 7) gas_credit:(Maybe (VarUInteger 3))
        mode:int8 exit_code:int32 exit_arg:(Maybe int32)
        vm_steps:uint32
        vm_init_state_hash:bits256 vm_final_state_hash:bits256
    ] = TrComputePhase;
    """
    def __init__(self,
                 type_: typing.Literal["skipped", "vm"],
                 reason: typing.Optional[ComputeSkipReason] = None,
                 success: bool = None,
                 msg_state_used: bool = None,
                 account_activated: bool = None,
                 gas_fees: int = None,
                 gas_used: int = None,
                 gas_limit: int = None,
                 gas_credit: typing.Optional[int] = None,
                 mode: int = None,
                 exit_code: int = None,
                 exit_arg: typing.Optional[int] = None,
                 vm_steps: int = None,
                 vm_init_state_hash: bytes = None,
                 vm_final_state_hash: bytes = None
                 ):
        self.type_ = type_
        if type_ == 'skipped':
            self.reason = reason
            return
        self.success = success
        self.msg_state_used = msg_state_used
        self.account_activated = account_activated
        self.gas_fees = gas_fees
        self.gas_used = gas_used
        self.gas_limit = gas_limit
        self.gas_credit = gas_credit
        self.mode = mode
        self.exit_code = exit_code
        self.exit_arg = exit_arg
        self.vm_steps = vm_steps
        self.vm_init_state_hash = vm_init_state_hash
        self.vm_final_state_hash = vm_final_state_hash

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        """
        tr_phase_compute_vm$1 success:Bool msg_state_used:Bool
        account_activated:Bool gas_fees:Grams
        ^[
            gas_used:(VarUInteger 7)
            gas_limit:(VarUInteger 7) gas_credit:(Maybe (VarUInteger 3))
            mode:int8 exit_code:int32 exit_arg:(Maybe int32)
            vm_steps:uint32
            vm_init_state_hash:bits256 vm_final_state_hash:bits256
        ] = TrComputePhase;
        """
        tag = cell_slice.load_bit()
        if not tag:
            return cls('skipped', ComputeSkipReason.deserialize(cell_slice))
        success = cell_slice.load_bool()
        msg_state_used = cell_slice.load_bool()
        account_activated = cell_slice.load_bool()
        gas_fees = cell_slice.load_coins()
        ref = cell_slice.load_ref().begin_parse()
        gas_used = ref.load_var_uint(3)  # int(7).bit_length()
        gas_limit = ref.load_var_uint(3)  # int(7).bit_length()
        gas_credit = ref.load_var_uint(2) if ref.load_bit() else None
        mode = ref.load_int(8)
        exit_code = ref.load_int(32)
        exit_arg = ref.load_int(32) if ref.load_bit() else None
        vm_steps = ref.load_uint(32)
        vm_init_state_hash = ref.load_bytes(32)
        vm_final_state_hash = ref.load_bytes(32)
        return cls(
            type_='vm',
            reason=None,
            success=success,
            msg_state_used=msg_state_used,
            account_activated=account_activated,
            gas_fees=gas_fees,
            gas_used=gas_used,
            gas_limit=gas_limit,
            gas_credit=gas_credit,
            mode=mode,
            exit_code=exit_code,
            exit_arg=exit_arg,
            vm_steps=vm_steps,
            vm_init_state_hash=vm_init_state_hash,
            vm_final_state_hash=vm_final_state_hash,
        )


class TrActionPhase(TlbScheme):
    """
    tr_phase_action$_ success:Bool valid:Bool no_funds:Bool
    status_change:AccStatusChange
    total_fwd_fees:(Maybe Grams) total_action_fees:(Maybe Grams)
    result_code:int32 result_arg:(Maybe int32) tot_actions:uint16
    spec_actions:uint16 skipped_actions:uint16 msgs_created:uint16
    action_list_hash:bits256 tot_msg_size:StorageUsedShort
    = TrActionPhase;
    """
    def __init__(self,
                 success: bool,
                 valid: bool,
                 no_funds: bool,
                 status_change: AccStatusChange,
                 total_fwd_fees: typing.Optional[int],
                 total_action_fees: typing.Optional[int],
                 result_code: int,
                 result_arg: typing.Optional[int],
                 tot_actions: int,
                 spec_actions: int,
                 skipped_actions: int,
                 msgs_created: int,
                 action_list_hash: bytes,
                 tot_msg_size: StorageUsedShort):
        self.success = success
        self.valid = valid
        self.no_funds = no_funds
        self.status_change = status_change
        self.total_fwd_fees = total_fwd_fees
        self.total_action_fees = total_action_fees
        self.result_code = result_code
        self.result_arg = result_arg
        self.tot_actions = tot_actions
        self.spec_actions = spec_actions
        self.skipped_actions = skipped_actions
        self.msgs_created = msgs_created
        self.action_list_hash = action_list_hash
        self.tot_msg_size = tot_msg_size

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(
            success=cell_slice.load_bool(),
            valid=cell_slice.load_bool(),
            no_funds=cell_slice.load_bool(),
            status_change=AccStatusChange.deserialize(cell_slice),
            total_fwd_fees=cell_slice.load_coins() if cell_slice.load_bit() else None,
            total_action_fees=cell_slice.load_coins() if cell_slice.load_bit() else None,
            result_code=cell_slice.load_int(32),
            result_arg=cell_slice.load_int(32) if cell_slice.load_bit() else None,
            tot_actions=cell_slice.load_uint(16),
            spec_actions=cell_slice.load_uint(16),
            skipped_actions=cell_slice.load_uint(16),
            msgs_created=cell_slice.load_uint(16),
            action_list_hash=cell_slice.load_bytes(32),
            tot_msg_size=StorageUsedShort.deserialize(cell_slice)
        )


class TrBouncePhase(TlbScheme):
    """
    tr_phase_bounce_negfunds$00 = TrBouncePhase;

    tr_phase_bounce_nofunds$01 msg_size:StorageUsedShort
    req_fwd_fees:Grams = TrBouncePhase;

    tr_phase_bounce_ok$1 msg_size:StorageUsedShort
    msg_fees:Grams fwd_fees:Grams = TrBouncePhase;
    """
    def __init__(self,
                 type_: typing.Literal["negfunds", "nofunds", "ok"],
                 msg_size: typing.Optional[StorageUsedShort] = None,
                 req_fwd_fees: typing.Optional[int] = None,
                 msg_fees: typing.Optional[int] = None,
                 fwd_fees: typing.Optional[int] = None
                 ):
        self.type_ = type_
        if type_ == 'negfunds':
            return
        if type_ == 'nofunds':
            self.msg_size = msg_size
            self.req_fwd_fees = req_fwd_fees
            return
        self.msg_size = msg_size
        self.msg_fees = msg_fees
        self.fwd_fees = fwd_fees

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_bit()
        if tag:  # 1
            return cls(
                'ok',
                msg_size=StorageUsedShort.deserialize(cell_slice),
                msg_fees=cell_slice.load_coins(),
                fwd_fees=cell_slice.load_coins()
            )
        tag = cell_slice.load_bit()
        if tag:  # 01
            return cls(
                'nofunds',
                msg_size=StorageUsedShort.deserialize(cell_slice),
                req_fwd_fees=cell_slice.load_coins(),
            )
        # 00
        return cls('negfunds')


""" ########## TR DESCRIPTIONS ########## """


class TransactionDescr(TlbScheme):
    """
    trans_ord$0000 credit_first:Bool storage_ph:(Maybe TrStoragePhase) credit_ph:(Maybe TrCreditPhase)
    compute_ph:TrComputePhase action:(Maybe ^TrActionPhase) aborted:Bool bounce:(Maybe TrBouncePhase)
    destroyed:Bool = TransactionDescr;

    trans_storage$0001 storage_ph:TrStoragePhase = TransactionDescr;

    trans_tick_tock$001 is_tock:Bool storage_ph:TrStoragePhase compute_ph:TrComputePhase
     action:(Maybe ^TrActionPhase) aborted:Bool destroyed:Bool = TransactionDescr;

    trans_split_prepare$0100 split_info:SplitMergeInfo storage_ph:(Maybe TrStoragePhase)
    compute_ph:TrComputePhase action:(Maybe ^TrActionPhase) aborted:Bool destroyed:Bool
    = TransactionDescr;

    trans_split_install$0101 split_info:SplitMergeInfo prepare_transaction:^Transaction
    installed:Bool = TransactionDescr;

    trans_merge_prepare$0110 split_info:SplitMergeInfo storage_ph:TrStoragePhase aborted:Bool
    = TransactionDescr;

    trans_merge_install$0111 split_info:SplitMergeInfo prepare_transaction:^Transaction
    storage_ph:(Maybe TrStoragePhase) credit_ph:(Maybe TrCreditPhase)
    compute_ph:TrComputePhase action:(Maybe ^TrActionPhase) aborted:Bool destroyed:Bool
    = TransactionDescr;
    """
    def __init__(self):
        ...

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_bits(3).to01()
        if tag == '001':
            return TransactionTickTock.deserialize(cell_slice)

        tag += str(cell_slice.load_bit())
        if tag == '0000':
            return TransactionOrdinary.deserialize(cell_slice)
        if tag == '0100':
            return TransactionSplitPrepare.deserialize(cell_slice)
        if tag == '0101':
            return TransactionSplitInstall.deserialize(cell_slice)
        if tag == '0110':
            return TransactionMergePrepare.deserialize(cell_slice)
        if tag == '0111':
            return TransactionMergeInstall.deserialize(cell_slice)

        raise TransactionError(f'TransactionDescr deserialization error unexpected tag: {tag}')


class TransactionOrdinary(TlbScheme):
    """
    trans_ord$0000 credit_first:Bool storage_ph:(Maybe TrStoragePhase) credit_ph:(Maybe TrCreditPhase)
    compute_ph:TrComputePhase action:(Maybe ^TrActionPhase) aborted:Bool bounce:(Maybe TrBouncePhase)
    destroyed:Bool = TransactionDescr;
    """

    def __init__(self,
                 credit_first: bool,
                 storage_ph: typing.Optional["TrStoragePhase"],
                 credit_ph: typing.Optional["TrCreditPhase"],
                 compute_ph: typing.Optional["TrComputePhase"],
                 action: typing.Optional["TrActionPhase"],
                 aborted: bool,
                 bounce: typing.Optional["TrBouncePhase"],
                 destroyed: bool):
        self.type_ = 'ordinary'
        self.credit_first = credit_first
        self.storage_ph = storage_ph
        self.credit_ph = credit_ph
        self.compute_ph = compute_ph
        self.action = action
        self.aborted = aborted
        self.bounce = bounce
        self.destroyed = destroyed

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(
            credit_first=cell_slice.load_bool(),
            storage_ph=TrStoragePhase.deserialize(cell_slice) if cell_slice.load_bit() else None,
            credit_ph=TrCreditPhase.deserialize(cell_slice) if cell_slice.load_bit() else None,
            compute_ph=TrComputePhase.deserialize(cell_slice),
            action=TrActionPhase.deserialize(cell_slice.load_ref().begin_parse()) if cell_slice.load_bit() else None,
            aborted=cell_slice.load_bool(),
            bounce=TrBouncePhase.deserialize(cell_slice) if cell_slice.load_bit() else None,
            destroyed=cell_slice.load_bool()
        )


class TransactionStorage(TlbScheme):
    """
    trans_storage$0001 storage_ph:TrStoragePhase = TransactionDescr;
    """
    def __init__(self,
                 storage_ph: TrStoragePhase,
                 ):
        self.type_ = 'storage'
        self.storage_ph = storage_ph

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(
            storage_ph=TrStoragePhase.deserialize(cell_slice),
        )


class TransactionTickTock(TlbScheme):
    """
    trans_tick_tock$001 is_tock:Bool storage_ph:TrStoragePhase compute_ph:TrComputePhase
    action:(Maybe ^TrActionPhase) aborted:Bool destroyed:Bool = TransactionDescr;
    """
    def __init__(self,
                 is_tock: bool,
                 storage_ph: TrStoragePhase,
                 compute_ph: TrComputePhase,
                 action: typing.Optional[TrActionPhase],
                 aborted: bool,
                 destroyed: bool):
        self.type_ = 'tick_tock'
        self.is_tock = is_tock
        self.storage_ph = storage_ph
        self.compute_ph = compute_ph
        self.action = action
        self.aborted = aborted
        self.destroyed = destroyed

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(
            is_tock=cell_slice.load_bool(),
            storage_ph=TrStoragePhase.deserialize(cell_slice),
            compute_ph=TrComputePhase.deserialize(cell_slice),
            action=TrActionPhase.deserialize(cell_slice.load_ref().begin_parse()) if cell_slice.load_bit() else None,
            aborted=cell_slice.load_bool(),
            destroyed=cell_slice.load_bool()
        )


class SplitMergeInfo(TlbScheme):
    """
    split_merge_info$_ cur_shard_pfx_len:(## 6)
    acc_split_depth:(## 6) this_addr:bits256 sibling_addr:bits256
    = SplitMergeInfo;
    """
    def __init__(self,
                 cur_shard_pfx_len: int,
                 acc_split_depth: int,
                 this_addr: bytes,
                 sibling_addr: bytes):
        self.cur_shard_pfx_len = cur_shard_pfx_len
        self.acc_split_depth = acc_split_depth
        self.this_addr = this_addr.hex()
        self.sibling_addr = sibling_addr.hex()

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(
            cur_shard_pfx_len=cell_slice.load_uint(6),
            acc_split_depth=cell_slice.load_uint(6),
            this_addr=cell_slice.load_bytes(32),
            sibling_addr=cell_slice.load_bytes(32)
        )


class TransactionSplitPrepare(TlbScheme):
    """
    trans_split_prepare$0100 split_info:SplitMergeInfo storage_ph:(Maybe TrStoragePhase)
    compute_ph:TrComputePhase action:(Maybe ^TrActionPhase) aborted:Bool destroyed:Bool
    = TransactionDescr;
    """
    def __init__(self,
                 split_info: SplitMergeInfo,
                 storage_ph: typing.Optional[TrStoragePhase],
                 compute_ph: TrComputePhase,
                 action: typing.Optional[TrActionPhase],
                 aborted: bool,
                 destroyed: bool):
        self.type_ = 'split_prepare'
        self.split_info = split_info
        self.storage_ph = storage_ph
        self.compute_ph = compute_ph
        self.action = action
        self.aborted = aborted
        self.destroyed = destroyed

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(
            split_info=SplitMergeInfo.deserialize(cell_slice),
            storage_ph=TrStoragePhase.deserialize(cell_slice) if cell_slice.load_bit() else None,
            compute_ph=TrComputePhase.deserialize(cell_slice),
            action=TrActionPhase.deserialize(cell_slice.load_ref().begin_parse()) if cell_slice.load_bit() else None,
            aborted=cell_slice.load_bool(),
            destroyed=cell_slice.load_bool()
        )


class TransactionSplitInstall(TlbScheme):
    """
    trans_split_install$0101 split_info:SplitMergeInfo
    prepare_transaction:^Transaction installed:Bool
    = TransactionDescr;
    """
    def __init__(self,
                 split_info: SplitMergeInfo,
                 prepare_transaction: Transaction,
                 installed: bool):
        self.type_ = 'split_install'
        self.split_info = split_info
        self.prepare_transaction = prepare_transaction
        self.installed = installed

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(
            split_info=SplitMergeInfo.deserialize(cell_slice),
            prepare_transaction=Transaction.deserialize(cell_slice.load_ref().begin_parse()),
            installed=cell_slice.load_bool()
        )


class TransactionMergePrepare(TlbScheme):
    """
    trans_merge_prepare$0110 split_info:SplitMergeInfo
    storage_ph:TrStoragePhase aborted:Bool
    = TransactionDescr;
    """
    def __init__(self,
                 split_info: SplitMergeInfo,
                 storage_ph: TrStoragePhase,
                 aborted: bool
                 ):
        self.type_ = 'merge_prepare'
        self.split_info = split_info
        self.storage_ph = storage_ph
        self.aborted = aborted

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(
            split_info=SplitMergeInfo.deserialize(cell_slice),
            storage_ph=TrStoragePhase.deserialize(cell_slice),
            aborted=cell_slice.load_bool()
        )


class TransactionMergeInstall(TlbScheme):
    """
    trans_merge_install$0111 split_info:SplitMergeInfo
    prepare_transaction:^Transaction storage_ph:(Maybe TrStoragePhase)
    credit_ph:(Maybe TrCreditPhase)
    compute_ph:TrComputePhase action:(Maybe ^TrActionPhase)
    aborted:Bool destroyed:Bool
    = TransactionDescr;
    """
    def __init__(self,
                 split_info: SplitMergeInfo,
                 prepare_transaction: Transaction,
                 storage_ph: typing.Optional[TrStoragePhase],
                 credit_ph: typing.Optional[TrCreditPhase],
                 compute_ph: TrComputePhase,
                 action: typing.Optional[TrActionPhase],
                 aborted: bool,
                 destroyed: bool
                 ):
        self.type_ = 'merge_install'
        self.split_info = split_info
        self.prepare_transaction = prepare_transaction
        self.storage_ph = storage_ph
        self.credit_ph = credit_ph
        self.compute_ph = compute_ph
        self.action = action
        self.aborted = aborted
        self.destroyed = destroyed

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        """
        trans_merge_install$0111 split_info:SplitMergeInfo
        prepare_transaction:^Transaction storage_ph:(Maybe TrStoragePhase)
        credit_ph:(Maybe TrCreditPhase)
        compute_ph:TrComputePhase action:(Maybe ^TrActionPhase)
        aborted:Bool destroyed:Bool
        = TransactionDescr;
        """
        return cls(
            split_info=SplitMergeInfo.deserialize(cell_slice),
            prepare_transaction=Transaction.deserialize(cell_slice.load_ref().begin_parse()),
            storage_ph=TrStoragePhase.deserialize(cell_slice) if cell_slice.load_bit() else None,
            credit_ph=TrCreditPhase.deserialize(cell_slice) if cell_slice.load_bit() else None,
            compute_ph=TrComputePhase.deserialize(cell_slice),
            action=TrActionPhase.deserialize(cell_slice.load_ref().begin_parse()) if cell_slice.load_bit() else None,
            aborted=cell_slice.load_bool(),
            destroyed=cell_slice.load_bool()
        )


class IntermediateAddress(TlbScheme):  # TODO: maybe move to account.py
    """
    interm_addr_regular$0 use_dest_bits:(#<= 96)
    = IntermediateAddress;

    interm_addr_simple$10 workchain_id:int8 addr_pfx:uint64
    = IntermediateAddress;

    interm_addr_ext$11 workchain_id:int32 addr_pfx:uint64
    = IntermediateAddress;
    """

    def __init__(self,
                 type_: str,
                 use_dest_bits: typing.Optional[int] = None,
                 workchain_id: typing.Optional[int] = None,
                 addr_pfx: typing.Optional[int] = None
                 ):
        self.type_ = type_
        self.use_dest_bits = use_dest_bits
        self.workchain_id = workchain_id
        self.addr_pfx = addr_pfx

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_bit()
        if not tag:  # 0
            return cls('interm_addr_regular', use_dest_bits=cell_slice.load_uint(7))
        tag = cell_slice.load_bit()
        if tag:  # 10
            return cls('interm_addr_simple', workchain_id=cell_slice.load_int(8), addr_pfx=cell_slice.load_uint(64))
        # 11
        return cls('interm_addr_ext', workchain_id=cell_slice.load_int(32), addr_pfx=cell_slice.load_uint(64))


class MsgEnvelope(TlbScheme):
    """
    msg_envelope#4 cur_addr:IntermediateAddress
    next_addr:IntermediateAddress fwd_fee_remaining:Grams
    msg:^(Message Any) = MsgEnvelope;
    """

    def __init__(self,
                 cur_addr: IntermediateAddress,
                 next_addr: IntermediateAddress,
                 fwd_fee_remaining: int,
                 msg: MessageAny):
        self.cur_addr = cur_addr
        self.next_addr = next_addr
        self.fwd_fee_remaining = fwd_fee_remaining
        self.msg = msg

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_uint(4)
        if tag != 4:
            raise TransactionError(f'MsgEnvelope deserialization error tag: {tag}')
        return cls(
            cur_addr=IntermediateAddress.deserialize(cell_slice),
            next_addr=IntermediateAddress.deserialize(cell_slice),
            fwd_fee_remaining=cell_slice.load_coins(),
            msg=MessageAny.deserialize(cell_slice.load_ref().begin_parse())
        )


class InMsg(TlbScheme):
    """
    msg_import_ext$000 msg:^(Message Any) transaction:^Transaction = InMsg;

    msg_import_ihr$010 msg:^(Message Any) transaction:^Transaction
        ihr_fee:Grams proof_created:^Cell = InMsg;

    msg_import_imm$011 in_msg:^MsgEnvelope
        transaction:^Transaction fwd_fee:Grams = InMsg;

    msg_import_fin$100 in_msg:^MsgEnvelope
        transaction:^Transaction fwd_fee:Grams = InMsg;

    msg_import_tr$101  in_msg:^MsgEnvelope out_msg:^MsgEnvelope
        transit_fee:Grams = InMsg;

    msg_discard_fin$110 in_msg:^MsgEnvelope transaction_id:uint64
        fwd_fee:Grams = InMsg;

    msg_discard_tr$111 in_msg:^MsgEnvelope transaction_id:uint64
        fwd_fee:Grams proof_delivered:^Cell = InMsg;
    """
    def __init__(self,
                 type_: str,
                 msg: typing.Optional[MessageAny] = None,
                 in_msg: typing.Optional[MsgEnvelope] = None,
                 transaction: typing.Optional[Transaction] = None,
                 **kwargs
                 ):
        self.type_ = type_
        self.msg = msg
        self.in_msg = in_msg
        self.transaction = transaction
        for k, v in kwargs.items():
            setattr(self, k, v)

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_bits(3).to01()
        if tag == '000':
            return cls('msg_import_ext',
                       msg=MessageAny.deserialize(cell_slice.load_ref().begin_parse()),
                       transaction=Transaction.deserialize(cell_slice.load_ref().begin_parse())
                       )
        if tag == '010':
            return cls('msg_import_ihr',
                       msg=MessageAny.deserialize(cell_slice.load_ref().begin_parse()),
                       transaction=Transaction.deserialize(cell_slice.load_ref().begin_parse()),
                       ihr_fee=cell_slice.load_coins(),
                       proof_created=cell_slice.load_ref()
                       )
        if tag == '011':
            return cls('msg_import_imm',
                       in_msg=MsgEnvelope.deserialize(cell_slice.load_ref().begin_parse()),
                       transaction=Transaction.deserialize(cell_slice.load_ref().begin_parse()),
                       fwd_fee=cell_slice.load_coins(),
                       )
        if tag == '100':
            return cls('msg_import_fin',
                       in_msg=MsgEnvelope.deserialize(cell_slice.load_ref().begin_parse()),
                       transaction=Transaction.deserialize(cell_slice.load_ref().begin_parse()),
                       fwd_fee=cell_slice.load_coins(),
                       )
        if tag == '101':
            return cls('msg_import_tr',
                       in_msg=MsgEnvelope.deserialize(cell_slice.load_ref().begin_parse()),
                       out_msg=MsgEnvelope.deserialize(cell_slice.load_ref().begin_parse()),
                       transit_fee=cell_slice.load_coins(),
                       )
        if tag == '110':
            return cls('msg_discard_fin',
                       in_msg=MsgEnvelope.deserialize(cell_slice.load_ref().begin_parse()),
                       transaction_id=cell_slice.load_uint(64),
                       transit_fee=cell_slice.load_coins(),
                       )
        if tag == '111':
            return cls('msg_discard_tr',
                       in_msg=MsgEnvelope.deserialize(cell_slice.load_ref().begin_parse()),
                       transaction_id=cell_slice.load_uint(64),
                       fwd_fee=cell_slice.load_coins(),
                       proof_delivered=cell_slice.load_ref()
                       )
        raise TransactionError(f'InMsg deserialization error: unknown prefix tag {tag}')


class OutMsg(TlbScheme):
    """
    msg_export_ext$000 msg:^(Message Any)
    transaction:^Transaction = OutMsg;

    msg_export_imm$010 out_msg:^MsgEnvelope
    transaction:^Transaction reimport:^InMsg = OutMsg;

    msg_export_new$001 out_msg:^MsgEnvelope
    transaction:^Transaction = OutMsg;

    msg_export_tr$011  out_msg:^MsgEnvelope
    imported:^InMsg = OutMsg;

    msg_export_deq$1100 out_msg:^MsgEnvelope
    import_block_lt:uint63 = OutMsg;

    msg_export_deq_short$1101 msg_env_hash:bits256
    next_workchain:int32 next_addr_pfx:uint64
    import_block_lt:uint64 = OutMsg;

    msg_export_tr_req$111 out_msg:^MsgEnvelope
    imported:^InMsg = OutMsg;

    msg_export_deq_imm$100 out_msg:^MsgEnvelope
    reimport:^InMsg = OutMsg;
    """
    def __init__(self,
                 type_: str,
                 msg: typing.Optional[MessageAny] = None,
                 out_msg: typing.Optional[MsgEnvelope] = None,
                 transaction: typing.Optional[Transaction] = None,
                 **kwargs
                 ):
        self.type_ = type_
        self.msg = msg
        self.out_msg = out_msg
        self.transaction = transaction
        for k, v in kwargs.items():
            setattr(self, k, v)

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.load_bits(3).to01()
        if tag == '000':
            return cls('msg_export_ext',
                       msg=MessageAny.deserialize(cell_slice.load_ref().begin_parse()),
                       transaction=Transaction.deserialize(cell_slice.load_ref().begin_parse())
                       )
        if tag == '010':
            return cls('msg_export_imm',
                       out_msg=MsgEnvelope.deserialize(cell_slice.load_ref().begin_parse()),
                       transaction=Transaction.deserialize(cell_slice.load_ref().begin_parse()),
                       reimport=InMsg.deserialize(cell_slice.load_ref().begin_parse()),
                       )
        if tag == '001':
            return cls('msg_export_new',
                       out_msg=MsgEnvelope.deserialize(cell_slice.load_ref().begin_parse()),
                       transaction=Transaction.deserialize(cell_slice.load_ref().begin_parse()),
                       )
        if tag == '011':
            return cls('msg_export_tr',
                       out_msg=MsgEnvelope.deserialize(cell_slice.load_ref().begin_parse()),
                       imported=InMsg.deserialize(cell_slice.load_ref().begin_parse()),
                       )
        if tag == '100':
            return cls('msg_export_deq_imm',
                       out_msg=MsgEnvelope.deserialize(cell_slice.load_ref().begin_parse()),
                       reimport=InMsg.deserialize(cell_slice.load_ref().begin_parse()),
                       )
        if tag == '111':
            return cls('msg_export_tr_req',
                       out_msg=MsgEnvelope.deserialize(cell_slice.load_ref().begin_parse()),
                       imported=InMsg.deserialize(cell_slice.load_ref().begin_parse()),
                       )
        tag += str(cell_slice.load_bit())
        if tag == '1100':
            return cls('msg_export_deq',
                       out_msg=MsgEnvelope.deserialize(cell_slice.load_ref().begin_parse()),
                       import_block_lt=cell_slice.load_uint(63)
                       )
        if tag == '1101':
            return cls('msg_export_deq',
                       msg_env_hash=cell_slice.load_bytes(32),
                       next_workchain=cell_slice.load_int(32),
                       next_addr_pfx=cell_slice.load_uint(64),
                       import_block_lt=cell_slice.load_uint(64)
                       )
        raise TransactionError(f'OutMsg deserialization error: unknown prefix tag {tag}')


class ImportFees(TlbScheme):
    """
    import_fees$_ fees_collected:Grams
    value_imported:CurrencyCollection = ImportFees;
    """

    def __init__(self, fees_collected: int, value_imported: CurrencyCollection):
        self.fees_collected = fees_collected
        self.value_imported = value_imported

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(fees_collected=cell_slice.load_coins(), value_imported=CurrencyCollection.deserialize(cell_slice))
