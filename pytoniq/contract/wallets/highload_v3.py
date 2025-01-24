import typing
from .wallet import Wallet, WalletError
from ..utils import HighloadQueryId
from ..contract import ContractError
from ...liteclient import LiteClientLike
from pytoniq_core.crypto.keys import private_key_to_public_key, mnemonic_to_private_key, mnemonic_is_valid, mnemonic_new
from pytoniq_core.crypto.signature import sign_message
from pytoniq_core.boc import Cell, Builder
from pytoniq_core.boc.address import Address
from pytoniq_core.tlb.account import StateInit
from pytoniq_core.tlb.custom.wallet import WalletMessage, HighloadWalletV3Data

HIGHLOAD_WALLET_V3_CODE = Cell.one_from_boc('b5ee9c7241021001000228000114ff00f4a413f4bcf2c80b01020120020d02014803040078d020d74bc00101c060b0915be101d0d3030171b0915be0fa4030f828c705b39130e0d31f018210ae42e5a4ba9d8040d721d74cf82a01ed55fb04e030020120050a02027306070011adce76a2686b85ffc00201200809001aabb6ed44d0810122d721d70b3f0018aa3bed44d08307d721d70b1f0201200b0c001bb9a6eed44d0810162d721d70b15800e5b8bf2eda2edfb21ab09028409b0ed44d0810120d721f404f404d33fd315d1058e1bf82325a15210b99f326df82305aa0015a112b992306dde923033e2923033e25230800ef40f6fa19ed021d721d70a00955f037fdb31e09130e259800ef40f6fa19cd001d721d70a00937fdb31e0915be270801f6f2d48308d718d121f900ed44d0d3ffd31ff404f404d33fd315d1f82321a15220b98e12336df82324aa00a112b9926d32de58f82301de541675f910f2a106d0d31fd4d307d30dd309d33fd315d15168baf2a2515abaf2a6f8232aa15250bcf2a304f823bbf2a35304800ef40f6fa199d024d721d70a00f2649130e20e01fe5309800ef40f6fa18e13d05004d718d20001f264c858cf16cf8301cf168e1030c824cf40cf8384095005a1a514cf40e2f800c94039800ef41704c8cbff13cb1ff40012f40012cb3f12cb15c9ed54f80f21d0d30001f265d3020171b0925f03e0fa4001d70b01c000f2a5fa4031fa0031f401fa0031fa00318060d721d300010f0020f265d2000193d431d19130e272b1fb00f984f3eb')
    
class HighloadWalletV3(Wallet):

    @classmethod
    async def from_data(cls, provider: LiteClientLike, public_key: bytes, timeout: typing.Optional[int] = None, wc: int = 0,
                        wallet_id: typing.Optional[int] = None, **kwargs) -> "HighloadWalletV3":
        data = cls.create_data_cell(public_key, wallet_id, wc, timeout)
        return await super().from_code_and_data(provider, wc, HIGHLOAD_WALLET_V3_CODE, data, **kwargs)

    @staticmethod
    def create_data_cell(public_key: bytes, wallet_id: typing.Optional[int] = None, wc: typing.Optional[int] = 0,
                         old_queries: typing.Optional[dict] = None, queries: typing.Optional[dict] = None, timeout: typing.Optional[int] = 128) -> Cell:
        if wallet_id is None:
            wallet_id = 698983191 + wc
        return HighloadWalletV3Data(public_key=public_key, wallet_id=wallet_id, old_queries=old_queries, queries=queries, last_cleaned=0, timeout=timeout).serialize()

    @classmethod
    async def from_private_key(cls, provider: LiteClientLike, private_key: bytes, wc: int = 0, wallet_id: typing.Optional[int] = None, timeout: typing.Optional[int] = None):
        public_key = private_key_to_public_key(private_key)
        return await cls.from_data(provider=provider, public_key=public_key, timeout=timeout, wc=wc, wallet_id=wallet_id, private_key=private_key)

    @classmethod
    async def from_mnemonic(cls, provider: LiteClientLike, mnemonics: typing.Union[list, str], wc: int = 0, wallet_id: typing.Optional[int] = None, timeout: typing.Optional[int] = None):
        if isinstance(mnemonics, str):
            mnemonics = mnemonics.split()
        assert mnemonic_is_valid(mnemonics), 'mnemonics are invalid!'
        _, private_key = mnemonic_to_private_key(mnemonics)
        return await cls.from_private_key(provider=provider, private_key=private_key, wc=wc, wallet_id=wallet_id, timeout=timeout)

    @classmethod
    async def create(cls, provider: LiteClientLike, wc: int = 0, wallet_id: typing.Optional[int] = None, timeout: typing.Optional[int] = None):
        """
        :param provider: provider
        :param wc: wallet workchain
        :param wallet_id: subwallet_id
        :param timeout: timeout
        :return: mnemonics and Wallet instance of provided version
        """
        mnemo = mnemonic_new(24)
        return mnemo, await cls.from_mnemonic(provider=provider, mnemonics=mnemo, wc=wc, wallet_id=wallet_id, timeout=timeout)

    @staticmethod
    def raw_create_transfer_msg(private_key: bytes, wallet_id: int, sendmode: int, created_at: int, timeout: int, message_to_send: WalletMessage, query_id: HighloadQueryId = 0) -> Cell:
        signing_message = Builder() \
            .store_uint(wallet_id, 32) \
            .store_ref(message_to_send) \
            .store_uint(sendmode, 8) \
            .store_uint(query_id.shift, 13) \
            .store_uint(query_id.bit_number, 10) \
            .store_uint(created_at, 64) \
            .store_uint(timeout, 22) \
        .end_cell()
        signature = sign_message(signing_message.hash, private_key)
        return Builder() \
            .store_bytes(signature) \
            .store_cell(signing_message) \
        .end_cell()

    async def raw_transfer(self, sendmode: int, created_at: int, timeout: int, msg: WalletMessage, query_id: HighloadQueryId = 0):
        """
        :param sendmode: sendmode
        :param created_at: created at
        :param timeout: timeout
        :param msg: WalletMessage. to create one call create_wallet_internal_message method
        :param query_id: query id
        """
        if 'private_key' not in self.__dict__:
            raise WalletError('must specify wallet private key!')

        transfer_msg = self.raw_create_transfer_msg(private_key=self.private_key, wallet_id=self.wallet_id, 
                                                    sendmode=sendmode, created_at=created_at, timeout=timeout,
                                                    message_to_send=msg, query_id=query_id)

        return await self.send_external(body=transfer_msg)

    async def transfer(self, destination: typing.Union[Address, str], amount: int, sendmode: int, created_at: int, timeout: int, body: Cell = Cell.empty(), state_init: StateInit = None):
        if isinstance(destination, str):
            destination = Address(destination)

            result_msg = self.create_wallet_internal_message(destination=destination, value=amount, body=body, state_init=state_init)
        return await self.raw_transfer(sendmode=sendmode, created_at=created_at, timeout=timeout, msg=result_msg)

    async def send_init_external(self, sendmode: int, created_at: int, timeout: int, message_to_send: WalletMessage):
        if not self.state_init:
            raise ContractError('contract does not have state_init attribute')
        if 'private_key' not in self.__dict__:
            raise WalletError('must specify wallet private key!')
        body = self.raw_create_transfer_msg(private_key=self.private_key, wallet_id=self.wallet_id, sendmode=sendmode, created_at=created_at, timeout=timeout, message_to_send=message_to_send)
        return await self.send_external(state_init=self.state_init, body=body)

    @property
    def wallet_id(self) -> int:
        """
        :return: wallet_id taken from contract data
        """
        return HighloadWalletV3Data.deserialize(self.state.data.begin_parse()).wallet_id

    @property
    def last_cleaned(self) -> int:
        """
        :return: last_cleaned taken from contract data
        """
        return HighloadWalletV3Data.deserialize(self.state.data.begin_parse()).last_cleaned
    
    @property
    def timeout(self) -> int:
        """
        :return: timeout taken from contract data
        """
        return HighloadWalletV3Data.deserialize(self.state.data.begin_parse()).timeout

    @property
    def public_key(self) -> bytes:
        """
        :return: public_key taken from contract data
        """
        return HighloadWalletV3Data.deserialize(self.state.data.begin_parse()).public_key

    @property
    def old_queries(self) -> dict:
        """
        :return: old_queries taken from contract data
        """
        return HighloadWalletV3Data.deserialize(self.state.data.begin_parse()).old_queries

    async def processed(self, query_id: int) -> bool:
        """
        :return: is query processed from wallet's get method
        """
        return (await super().run_get_method(method='processed?', stack=[query_id]))[0]