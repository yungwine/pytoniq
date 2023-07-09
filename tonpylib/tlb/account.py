import typing

from .tlb import TlbScheme, TlbError
from .utils import MerkleUpdate
from ..boc import Slice, Builder, Cell
from ..boc.address import Address


class SimpleAccount(TlbScheme):
    """
    // simple_balance$_ Grams = AccountBalance;

    account_none$0 = Account;
    account$1 addr:Address balance:Grams state:SimpleAccountState = Account;
    """
    """
    this schema is needed for user-friendly and familiar account representation,
    but not used anywhere outside of this library
    """
    def __init__(self, address: Address, balance: int, state: "SimpleAccountState"):
        self.address = address
        self.balance = balance
        self.state = state

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, *args):
        ...

    @classmethod
    def from_raw(cls, account: "Account"):
        return cls(address=account.addr, balance=account.storage.balance.grams, state=SimpleAccountState.from_raw(account.storage.state))

    def __repr__(self):
        return f'<SimpleAccount {self.address}: state={self.state.type_}, balance={self.balance}>'


class SimpleAccountState(TlbScheme):
    """
    uninitialized$00 = SimpleAccountState;
    frozen$01 state_hash:bits256 = SimpleAccountState;
    active$10 code:^Cell data:^Cell = SimpleAccountState;
    """
    """
    this schema is needed for user-friendly and familiar account state representation,
    but not used anywhere outside of this library
    """

    def __init__(self, type_: typing.Literal["uninitialized", "frozen", "active"],
                 state_hash: typing.Optional[bytes] = None,
                 code: typing.Optional[Cell] = None,
                 data: typing.Optional[Cell] = None,
                 ):
        self.type_ = type_
        self.state_hash = state_hash
        self.code = code
        self.data = data

    @classmethod
    def serialize(cls, *args):
        ...

    @classmethod
    def deserialize(cls, *args):
        ...

    @classmethod
    def from_raw(cls, account_state: "AccountState"):
        if account_state.type_ == 'account_uninit':
            return cls('uninitialized')
        if account_state.type_ == 'account_frozen':
            return cls('frozen', state_hash=account_state.state_hash)
        return cls('active', code=account_state.state_init.code, data=account_state.state_init.data)


class Account(TlbScheme):
    """
    account_none$0 = Account;
    account$1 addr:MsgAddressInt storage_stat:StorageInfo storage:AccountStorage = Account;
    """

    def __init__(self, addr: Address, storage_stat: "StorageInfo", storage: "AccountStorage"):
        self.addr = addr
        self.storage_stat = storage_stat
        self.storage = storage

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        if cell_slice.load_bit():
            return cls(cell_slice.load_address(), StorageInfo.deserialize(cell_slice), AccountStorage.deserialize(cell_slice))
        else:
            return None


class StorageInfo(TlbScheme):
    """
    storage_info$_ used:StorageUsed last_paid:uint32
              due_payment:(Maybe Grams) = StorageInfo;
    """

    def __init__(self, used: "StorageUsed", last_paid: int, due_payment: typing.Optional[int]):
        self.used = used
        self.last_paid = last_paid
        self.due_payment = due_payment

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(StorageUsed.deserialize(cell_slice), cell_slice.load_uint(32), cell_slice.load_coins() if cell_slice.load_bit() else None)


class StorageUsed(TlbScheme):
    """
    storage_used$_ cells:(VarUInteger 7) bits:(VarUInteger 7)
    public_cells:(VarUInteger 7) = StorageUsed;
    """

    def __init__(self, cells, bits, public_cells):
        self.cells = cells
        self.bits = bits
        self.public_cells = public_cells

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        l = 3  # int(7).bit_length()
        return cls(cell_slice.load_var_uint(l), cell_slice.load_var_uint(l), cell_slice.load_var_uint(l),)


class AccountStorage(TlbScheme):
    """
    account_storage$_ last_trans_lt:uint64
    balance:CurrencyCollection state:AccountState
    = AccountStorage;
    """

    def __init__(self, last_trans_lt: int, balance: "CurrencyCollection", state: "AccountState"):
        self.last_trans_lt = last_trans_lt
        self.balance = balance
        self.state = state

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        from .block import CurrencyCollection
        return cls(
            cell_slice.load_uint(64),
            CurrencyCollection.deserialize(cell_slice),
            AccountState.deserialize(cell_slice)
        )


class AccountState(TlbScheme):
    """
    account_uninit$00 = AccountState;
    account_active$1 _:StateInit = AccountState;
    account_frozen$01 state_hash:bits256 = AccountState;
    """

    def __init__(self, type_: str, **kwargs):
        self.type_ = type_
        self.state_init: StateInit
        self.state_hash: str
        for k, v in kwargs.items():
            setattr(self, k, v)

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        b = cell_slice.load_bit()
        kwargs = {}
        if b:  # $1
            type_ = 'account_active'
            kwargs['state_init'] = StateInit.deserialize(cell_slice)
        else:
            b = cell_slice.load_bit()
            if b:  # $01
                type_ = 'account_frozen'
                kwargs['state_hash'] = cell_slice.load_bytes(32).hex()
            else:  # $00
                type_ = 'account_uninit'
        return cls(type_, **kwargs)


class StateInit(TlbScheme):
    """
    _ split_depth:(Maybe (## 5)) special:(Maybe TickTock)
    code:(Maybe ^Cell) data:(Maybe ^Cell)
    library:(Maybe ^Cell) = StateInit;
    """

    def __init__(self,
                 split_depth: typing.Optional[int],
                 special: typing.Optional["TickTock"],
                 code: typing.Optional[Cell],
                 data: typing.Optional[Cell],
                 library: typing.Optional[Cell]):
        self.split_depth = split_depth
        self.special = special
        self.code = code
        self.data = data
        self.library = library

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(
            split_depth=cell_slice.load_uint(5) if cell_slice.load_bit() else None,
            special=TickTock.deserialize(cell_slice) if cell_slice.load_bit() else None,
            code=cell_slice.load_ref() if cell_slice.load_bit() else None,
            data=cell_slice.load_ref() if cell_slice.load_bit() else None,
            library=cell_slice.load_ref() if cell_slice.load_bit() else None,
        )


class TickTock(TlbScheme):
    """
    tick_tock$_ tick:Bool tock:Bool = TickTock;
    """
    def __init__(self, tick: bool, tock: bool):
        self.tick = tick
        self.tock = tock

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(cell_slice.load_bool(), cell_slice.load_bool())


class ShardAccount(TlbScheme):
    """
    account_descr$_ account:^Account last_trans_hash:bits256
    last_trans_lt:uint64 = ShardAccount;
    """
    def __init__(self, account: Account, last_trans_hash: bytes, last_trans_lt: int, cell: typing.Optional[Cell] = None):
        self.account = account
        self.last_trans_hash = last_trans_hash
        self.last_trans_lt = last_trans_lt
        self.cell = cell  # to check merkle proof of account states

    @classmethod
    def serialize(cls, *args):
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        cell_copy = cell_slice.copy()  # TODO optimize
        return cls(account=Account.deserialize(cell_slice.load_ref().begin_parse()),
                   last_trans_hash=cell_slice.load_bytes(32),
                   last_trans_lt=cell_slice.load_uint(64), cell=cell_copy.to_cell())
