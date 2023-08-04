import typing

from ..liteclient.client import LiteClient
from pytoniq_core.boc.cell import Cell
from pytoniq_core.boc.address import Address
from pytoniq_core.tlb.account import StateInit, Account, SimpleAccount, ShardAccount
from pytoniq_core.tlb.block import CurrencyCollection
from pytoniq_core.tlb.transaction import ExternalMsgInfo, MessageAny, InternalMsgInfo


class ContractError(BaseException):
    pass


class Contract:

    def __init__(self, provider: LiteClient, address: Address, account: typing.Optional[Account] = None,
                 shard_account: typing.Optional[ShardAccount] = None, state_init: typing.Optional[StateInit] = None,
                 **kwargs):
        """
        :param provider: LiteClient
        :param address: contract address
        :param account: full account state
        :param shard_account: shard account
        :param state_init: account state init. usually used for contract deploying
        :param kwargs: some additional account attributes. for e.g. private key for wallet contracts
        """
        self.provider = provider
        self.address = address
        self.raw_account: typing.Optional[Account] = None
        self.account: SimpleAccount = None
        self.shard_account: typing.Optional[ShardAccount] = None
        self.is_active: bool = None
        self.is_uninitialized: bool = None
        self.is_frozen: bool = None
        self.state: typing.Optional[StateInit] = None
        self.state_init: typing.Optional[StateInit] = state_init
        self.set_account_attributes(account, shard_account)

        for k, v in kwargs.items():
            setattr(self, k, v)

    def set_account_attributes(self, account: typing.Optional[Account], shard_account: typing.Optional[ShardAccount]):
        self.raw_account = account
        self.account = SimpleAccount.from_raw(account, self.address)
        self.shard_account = shard_account
        self.is_active = self.account.is_active()
        self.is_uninitialized = self.account.is_uninitialized()
        self.is_frozen = self.account.is_frozen()

        self.state = None
        if self.is_active:
            self.state = self.account.state.state_init
        else:
            self.state = self.state_init

    @property
    def data(self) -> Cell:
        return self.state.data

    @property
    def code(self) -> Cell:
        return self.state.code

    @property
    def balance(self) -> int:
        """
        :return: balance from saved account state
        """
        return self.account.balance

    @classmethod
    async def from_address(cls, provider: LiteClient, address: typing.Union[str, Address], **kwargs):
        if isinstance(address, str):
            address = Address(address)
        account, shard_account = await provider.raw_get_account_state(address)
        return cls(provider=provider, address=address, account=account, shard_account=shard_account, **kwargs)

    @classmethod
    async def from_state_init(cls, provider: LiteClient, workchain: int, state_init: StateInit, **kwargs):
        address = Address((workchain, state_init.serialize().hash))
        return await cls.from_address(provider=provider, address=address, state_init=state_init, **kwargs)

    @classmethod
    async def from_code_and_data(cls, provider: LiteClient, workchain: int, code: Cell, data: Cell, **kwargs):
        state_init = StateInit(code=code, data=data)
        return await cls.from_state_init(provider=provider, workchain=workchain, state_init=state_init, **kwargs)

    async def update(self):
        account, shard_account = await self.raw_get_account_state()
        self.set_account_attributes(account, shard_account)

    async def raw_get_account_state(self):
        return (await self.provider.raw_get_account_state(address=self.address))[0]

    async def get_account_state(self):
        return await self.provider.get_account_state(self.address)

    async def get_balance(self) -> int:
        """
        :return: balance from current account state. better to
            await contract.update()
            contract.balance
        """
        account_state = await self.get_account_state()
        return account_state.balance

    async def run_get_method(self, method: typing.Union[str, int], stack: typing.Optional[list] = None):
        if stack is None:
            stack = []
        return await self.provider.run_get_method(self.address, method, stack)

    @staticmethod
    def create_external_msg(src: typing.Optional[Address] = None, dest: typing.Optional[Address] = None,
                            import_fee: int = 0, state_init: typing.Optional[StateInit] = None,
                            body: Cell = None) -> MessageAny:
        info = ExternalMsgInfo(src, dest, import_fee)
        if body is None:
            body = Cell.empty()
        message = MessageAny(info=info, init=state_init, body=body)
        return message

    @staticmethod
    def create_internal_msg(ihr_disabled: bool = True, bounce: bool = None, bounced: bool = False, src: Address = None,
                            dest: Address = None,
                            value: typing.Union[CurrencyCollection, int] = 0, ihr_fee: int = 0, fwd_fee: int = 0,
                            created_lt: int = 0,
                            created_at: int = 0, state_init: typing.Optional[StateInit] = None,
                            body: Cell = None) -> MessageAny:
        if isinstance(value, int):
            value = CurrencyCollection(grams=value, other=None)
        if bounce is None:
            bounce = dest.is_bounceable
        info = InternalMsgInfo(ihr_disabled, bounce, bounced, src, dest, value, ihr_fee, fwd_fee, created_lt, created_at)
        if body is None:
            body = Cell.empty()
        message = MessageAny(info=info, init=state_init, body=body)
        return message

    async def send_external(self, src: typing.Optional[Address] = None, import_fee: int = 0,
                            state_init: typing.Optional[StateInit] = None, body: Cell = None):
        message = self.create_external_msg(src=src, dest=self.address, import_fee=import_fee, state_init=state_init,
                                           body=body)
        return await self.provider.raw_send_message(message.serialize().to_boc())

    async def send_init_external(self):
        if not self.state_init:
            raise ContractError('contract does not have state_init attribute')
        return await self.send_external(state_init=self.state_init)

    async def deploy_via_external(self):
        return await self.send_init_external()

    def __repr__(self):
        return f'<{self.account.state.type_} {self.__class__.__name__} {self.address}>'  # <active WalletV4R2 EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG>
