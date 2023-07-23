import time
import typing

from .wallet import Wallet, WalletError
from ..utils import generate_query_id
from ..contract import Contract, ContractError
from ...liteclient.client import LiteClient
from ...crypto.keys import private_key_to_public_key, mnemonic_to_private_key, mnemonic_is_valid, mnemonic_new
from ...crypto.signature import sign_message
from ...boc import Cell, Builder, HashMap
from ...boc.address import Address
from ...tlb.account import StateInit
from ...tlb.custom.wallet import HighloadWalletData, WalletMessage

HIGHLOAD_WALLET_CODE = Cell.one_from_boc(
    b'\xb5\xee\x9cr\x01\x01\t\x01\x00\xe5\x00\x01\x14\xff\x00\xf4\xa4\x13\xf4\xbc\xf2\xc8\x0b\x01\x02\x01 \x02\x03\x02\x01H\x04\x05\x01\xea\xf2\x83\x08\xd7\x18 \xd3\x1f\xd3?\xf8#\xaa\x1fS \xb9\xf2c\xedD\xd0\xd3\x1f\xd3?\xd3\xff\xf4\x04\xd1S`\x80@\xf4\x0eo\xa11\xf2`Qs\xba\xf2\xa2\x07\xf9\x01T\x10\x87\xf9\x10\xf2\xa3\x02\xf4\x04\xd1\xf8\x00\x7f\x8e\x16!\x80\x10\xf4xo\xa5 \x98\x02\xd3\x07\xd40\x01\xfb\x00\x912\xe2\x01\xb3\xe6[\x83%\xa1\xc8@4\x80@\xf4C\x8a\xe61\x01\xc8\xcb\x1f\x13\xcb?\xcb\xff\xf4\x00\xc9\xedT\x08\x00\x04\xd00\x02\x01 \x06\x07\x00\x17\xbd\x9c\xe7j&\x86\x9a\xf9\x8e\xb8_\xfc\x00A\xbe_\x97j&\x86\x98\xf9\x8e\x99\xfe\x9f\xf9\x8f\xa0&\x8a\x91\x04\x02\x07\xa0s}\t\x8c\x92\xdb\xfc\x95\xdd\x1f\x14\x004 \x80@\xf4\x96o\xa5l\x12 \x940S\x03\xb9\xde \x9336\x01\x92l!\xe2\xb3')


class HighloadWallet(Wallet):

    @classmethod
    async def from_data(cls, provider: LiteClient, public_key: bytes, wc: int = 0,
                        wallet_id: typing.Optional[int] = None, **kwargs) -> "HighloadWallet":
        data = cls.create_data_cell(public_key, wallet_id, wc)
        return await super().from_code_and_data(provider, wc, HIGHLOAD_WALLET_CODE, data, **kwargs)

    @staticmethod
    def create_data_cell(public_key: bytes, wallet_id: typing.Optional[int] = None, wc: typing.Optional[int] = 0,
                         old_queries: typing.Optional[dict] = None) -> Cell:
        if wallet_id is None:
            wallet_id = 698983191 + wc
        return HighloadWalletData(wallet_id=wallet_id, public_key=public_key, last_cleaned=0, old_queries=old_queries).serialize()

    @classmethod
    async def from_private_key(cls, provider: LiteClient, private_key: bytes, wc: int = 0,
                               wallet_id: typing.Optional[int] = None):
        public_key = private_key_to_public_key(private_key)
        return await cls.from_data(provider=provider, wc=wc, public_key=public_key, wallet_id=wallet_id,
                                   private_key=private_key)

    @classmethod
    async def from_mnemonic(cls, provider: LiteClient, mnemonics: typing.Union[list, str], wc: int = 0,
                            wallet_id: typing.Optional[int] = None):
        if isinstance(mnemonics, str):
            mnemonics = mnemonics.split()
        assert mnemonic_is_valid(mnemonics), 'mnemonics are invalid!'
        _, private_key = mnemonic_to_private_key(mnemonics)
        return await cls.from_private_key(provider, private_key, wc, wallet_id)

    @classmethod
    async def create(cls, provider: LiteClient, wc: int = 0, wallet_id: typing.Optional[int] = None):
        """
        :param provider: provider
        :param wc: wallet workchain
        :param wallet_id: subwallet_id
        :return: mnemonics and Wallet instance of provided version
        """
        mnemo = mnemonic_new(24)
        return mnemo, await cls.from_mnemonic(provider, mnemo, wc, wallet_id)

    @staticmethod
    def raw_create_transfer_msg(private_key: bytes, wallet_id: int, messages: typing.List[WalletMessage],
                                query_id: int = 0, offset: int = 7200) -> Cell:

        signing_message = Builder().store_uint(wallet_id, 32)
        if not query_id:
            signing_message.store_uint(generate_query_id(offset), 64)
        else:
            signing_message.store_uint(query_id, 64)

        def value_serializer(src, dest):
            dest.store_cell(src.serialize())

        messages_dict = HashMap(key_size=16, value_serializer=value_serializer)

        for i in range(len(messages)):
            messages_dict.set_int_key(i, messages[i])

        signing_message.store_dict(messages_dict.serialize())

        signing_message = signing_message.end_cell()
        signature = sign_message(signing_message.hash, private_key)
        return Builder() \
            .store_bytes(signature) \
            .store_cell(signing_message) \
            .end_cell()

    async def raw_transfer(self, msgs: typing.List[WalletMessage], query_id: int = 0, offset: int = 7200):
        """
        :param query_id: query id
        :param offset: if query id is 0 it will be generated as current_time + offset
        :param msgs: list of WalletMessages. to create one call create_wallet_internal_message meth
        """
        assert len(msgs) <= 254, 'for highload wallet maximum messages amount is 254'
        if 'private_key' not in self.__dict__:
            raise WalletError('must specify wallet private key!')

        transfer_msg = self.raw_create_transfer_msg(private_key=self.private_key, wallet_id=self.wallet_id,
                                                    query_id=query_id, offset=offset, messages=msgs)

        return await self.send_external(body=transfer_msg)

    async def transfer(self, destinations: typing.Union[Address, str], amounts: int, bodies: typing.List[Cell],
                       state_inits: typing.List[StateInit] = None):
        result_msgs = []
        for i in range(len(destinations)):
            destination = destinations[i]
            body = bodies[i]
            if body is None:
                body = Cell.empty()

            if isinstance(destination, str):
                destination = Address(destination)

            result_msgs.append(
                self.create_wallet_internal_message(destination=destination, value=amounts[i], body=body,
                                                    state_init=state_inits[i]))
        return await self.raw_transfer(msgs=result_msgs)

    async def send_init_external(self):
        if not self.state_init:
            raise ContractError('contract does not have state_init attribute')
        if 'private_key' not in self.__dict__:
            raise WalletError('must specify wallet private key!')
        body = self.raw_create_transfer_msg(private_key=self.private_key, wallet_id=self.wallet_id, messages=[])
        return await self.send_external(state_init=self.state_init, body=body)

    @property
    def wallet_id(self) -> int:
        """
        :return: wallet_id taken from contract data
        """
        return HighloadWalletData.deserialize(self.state.data.begin_parse()).wallet_id

    @property
    def last_cleaned(self) -> int:
        """
        :return: last_cleaned taken from contract data
        """
        return HighloadWalletData.deserialize(self.state.data.begin_parse()).last_cleaned

    @property
    def public_key(self) -> bytes:
        """
        :return: public_key taken from contract data
        """
        return HighloadWalletData.deserialize(self.state.data.begin_parse()).public_key

    @property
    def old_queries(self) -> dict:
        """
        :return: old_queries taken from contract data
        """
        return HighloadWalletData.deserialize(self.state.data.begin_parse()).old_queries

    async def processed(self, query_id: int) -> bool:
        """
        :return: is query processed from wallet's get method
        """
        return (await super().run_get_method(method='processed?', stack=[query_id]))[0]
