import time
import typing

from .wallet import Wallet, WalletError
from ..contract import ContractError
from ...liteclient import LiteClientLike
from pytoniq_core.crypto.keys import private_key_to_public_key, mnemonic_to_private_key, mnemonic_is_valid, mnemonic_new
from pytoniq_core.crypto.signature import sign_message
from pytoniq_core.boc import Cell, Builder, begin_cell
from pytoniq_core.boc.address import Address
from pytoniq_core.tlb.account import StateInit
from pytoniq_core.tlb.custom.wallet import HighloadWalletV3Data, WalletMessage

HIGHLOAD_V3_WALLET_CODE = Cell.one_from_boc(
    b'\xb5\xee\x9crA\x02\x10\x01\x00\x02(\x00\x01\x14\xff\x00\xf4\xa4\x13\xf4\xbc\xf2\xc8\x0b\x01\x02\x01 \x02\r\x02\x01H\x03\x04\x00x\xd0 \xd7K\xc0\x01\x01\xc0`\xb0\x91[\xe1\x01\xd0\xd3\x03\x01q\xb0\x91[\xe0\xfa@0\xf8(\xc7\x05\xb3\x910\xe0\xd3\x1f\x01\x82\x10\xaeB\xe5\xa4\xba\x9d\x80@\xd7!\xd7L\xf8*\x01\xedU\xfb\x04\xe00\x02\x01 \x05\n\x02\x02s\x06\x07\x00\x11\xad\xcev\xa2hk\x85\xff\xc0\x02\x01 \x08\t\x00\x1a\xab\xb6\xedD\xd0\x81\x01"\xd7!\xd7\x0b?\x00\x18\xaa;\xedD\xd0\x83\x07\xd7!\xd7\x0b\x1f\x02\x01 \x0b\x0c\x00\x1b\xb9\xa6\xee\xd4M\x08\x10\x16-r\x1dp\xb1X\x00\xe5\xb8\xbf.\xda.\xdf\xb2\x1a\xb0\x90(@\x9b\x0e\xd4M\x08\x10\x12\rr\x1f@O@M3\xfd1]\x10X\xe1\xbf\x822Z\x15!\x0b\x99\xf3&\xdf\x820Z\xa0\x01Z\x11+\x99#\x06\xdd\xe9#\x03>)#\x03>%#\x08\x00\xdf@\xf6\xfa\x19\xed\x02\x1dr\x1dp\xa0\tU\xf07\xfd\xb3\x1e\t\x13\x0e%\x98\x00\xdf@\xf6\xfa\x19\xcd\x00\x1dr\x1dp\xa0\t7\xfd\xb3\x1e\t\x15\xbe\'\x08\x01\xf6\xf2\xd4\x83\x08\xd7\x18\xd1!\xf9\x00\xedD\xd0\xd3\xff\xd3\x1f\xf4\x04\xf4\x04\xd3?\xd3\x15\xd1\xf8#!\xa1R \xb9\x8e\x123m\xf8#$\xaa\x00\xa1\x12\xb9\x92m2\xdeX\xf8#\x01\xdeT\x16u\xf9\x10\xf2\xa1\x06\xd0\xd3\x1f\xd4\xd3\x07\xd3\x0c\xd3\t\xd3?\xd3\x15\xd1Qh\xba\xf2\xa2QZ\xba\xf2\xa6\xf8#*\xa1RP\xbc\xf2\xa3\x04\xf8#\xbb\xf2\xa3S\x04\x80\r\xf4\x0fo\xa1\x99\xd0$\xd7!\xd7\n\x00\xf2d\x910\xe2\x0e\x01\xfeS\t\x80\r\xf4\x0fo\xa1\x8e\x13\xd0P\x04\xd7\x18\xd2\x00\x01\xf2d\xc8X\xcf\x16\xcf\x83\x01\xcf\x16\x8e\x100\xc8$\xcf@\xcf\x83\x84\tP\x05\xa1\xa5\x14\xcf@\xe2\xf8\x00\xc9@9\x80\r\xf4\x17\x04\xc8\xcb\xff\x13\xcb\x1f\xf4\x00\x12\xf4\x00\x12\xcb?\x12\xcb\x15\xc9\xedT\xf8\x0f!\xd0\xd3\x00\x01\xf2e\xd3\x02\x01q\xb0\x92_\x03\xe0\xfa@\x01\xd7\x0b\x01\xc0\x00\xf2\xa5\xfa@1\xfa\x001\xf4\x01\xfa\x001\xfa\x001\x80`\xd7!\xd3\x00\x01\x0f\x00 \xf2e\xd2\x00\x01\x93\xd41\xd1\x910\xe2r\xb1\xfb\x00\xb5\x85\xbf\x03')


class HighloadWalletV3(Wallet):

    @classmethod
    async def from_data(cls, provider: LiteClientLike, public_key: bytes, wc: int = 0,
                        wallet_id: typing.Optional[int] = None, **kwargs) -> "HighloadWalletV3":
        data = cls.create_data_cell(public_key, wallet_id, wc)
        return await super().from_code_and_data(provider, wc, HIGHLOAD_V3_WALLET_CODE, data, **kwargs)

    @staticmethod
    def create_data_cell(public_key: bytes, wallet_id: typing.Optional[int] = None, wc: typing.Optional[int] = 0,
                         old_queries: typing.Optional[dict] = None, queries: typing.Optional[dict] = None, timeout: typing.Optional[int] = 3600) -> Cell:
        if wallet_id is None:
            wallet_id = 0x10ad + wc
        return HighloadWalletV3Data(wallet_id=wallet_id, public_key=public_key, last_clean_time=0, old_queries=old_queries, queries=queries, timeout=timeout).serialize()

    @classmethod
    async def from_private_key(cls, provider: LiteClientLike, private_key: bytes, wc: int = 0,
                               wallet_id: typing.Optional[int] = None, timeout: typing.Optional[int] = 3600):
        public_key = private_key_to_public_key(private_key)
        return await cls.from_data(provider=provider, wc=wc, public_key=public_key, wallet_id=wallet_id,
                                   private_key=private_key)

    @classmethod
    async def from_mnemonic(cls, provider: LiteClientLike, mnemonics: typing.Union[list, str], wc: int = 0,
                            wallet_id: typing.Optional[int] = None, timeout: typing.Optional[int] = 3600):
        if isinstance(mnemonics, str):
            mnemonics = mnemonics.split()
        assert mnemonic_is_valid(mnemonics), 'mnemonics are invalid!'
        _, private_key = mnemonic_to_private_key(mnemonics)
        return await cls.from_private_key(provider, private_key, wc, wallet_id)

    @classmethod
    async def create(cls, provider: LiteClientLike, wc: int = 0, wallet_id: typing.Optional[int] = None, timeout: typing.Optional[int] = 3600):
        """
        :param provider: provider
        :param wc: wallet workchain
        :param wallet_id: subwallet_id
        :return: mnemonics and Wallet instance of provided version
        """
        mnemo = mnemonic_new(24)
        return mnemo, await cls.from_mnemonic(provider, mnemo, wc, wallet_id)

    def pack_actions(
            self,
            messages: typing.List[WalletMessage],
            query_id: int,
    ) -> WalletMessage:

        message_per_pack = 253

        if len(messages) > message_per_pack:
            rest = self.pack_actions(messages[message_per_pack:], query_id)
            messages = messages[:message_per_pack] + [rest]

        amt = 0
        list_cell = Cell.empty()

        for msg in messages:
            amt += msg.message.info.value.grams
            msg = (begin_cell()
                  .store_uint(0x0ec3c86d, 32)
                  .store_uint(msg.send_mode, 8)
                  .store_ref(msg.message.serialize())
                  .end_cell())
            list_cell = (
                begin_cell()
                .store_ref(list_cell)
                .store_cell(msg)
                .end_cell()
            )

        # attach some coins for internal message processing gas fees
        fees = 7*10**6 * len(messages) + 10**7  # 0.007 per message + 0.01 for all
        amt += fees

        return self.create_wallet_internal_message(
            destination=self.address,
            send_mode=3,
            value=amt,
            body=(
                begin_cell()
                .store_uint(0xae42e5a4, 32)
                .store_uint(query_id, 64)
                .store_ref(list_cell)
                .end_cell()
            )
        )

    def raw_create_transfer_msg(self, private_key: bytes, wallet_id: int, messages: typing.List[WalletMessage],
                                query_id: int = 0, timeout: int = None, created_at: int = None) -> Cell:

        if created_at is None:
            created_at = int(time.time()) - 30
        if query_id is None:
            query_id = created_at % (1 << 23)
        if timeout is None:
            timeout = self.timeout

        assert len(messages) > 0, 'messages should not be empty'
        assert len(messages) <= 254 * 254, 'for highload v3 wallet maximum messages amount is 254*254'
        assert timeout < (1 << 22), 'timeout is too big'
        assert timeout > 5, 'timeout is too small'
        assert query_id < (1 << 23), 'query id is too big'
        assert created_at > 0, 'created_at should be positive'

        if len(messages) == 1 and messages[0].message.init is None:
            msg = messages[0]
        else:
            msg = self.pack_actions(messages, query_id)

        signing_message = (
            begin_cell()
            .store_uint(wallet_id, 32)
            .store_ref(msg.message.serialize())
            .store_uint(msg.send_mode, 8)
            .store_uint(query_id, 23)
            .store_uint(created_at, 64)
            .store_uint(timeout, 22)
            .end_cell()
        )

        signature = sign_message(signing_message.hash, private_key)
        return Builder() \
            .store_bytes(signature) \
            .store_ref(signing_message) \
            .end_cell()

    async def raw_transfer(self, msgs: typing.List[WalletMessage], query_id: int = None, timeout: int = None):
        if 'private_key' not in self.__dict__:
            raise WalletError('must specify wallet private key!')

        transfer_msg = self.raw_create_transfer_msg(private_key=self.private_key, wallet_id=self.wallet_id,
                                                    query_id=query_id, timeout=timeout, messages=msgs)

        return await self.send_external(body=transfer_msg)

    async def transfer(self, destinations: typing.Union[typing.List[Address], typing.List[str]],
                    amounts: typing.List[int], bodies: typing.List[Cell],
                    state_inits: typing.List[StateInit] = None, query_id: int = None):
        # Check if all lists are of the same length
        if not (len(destinations) == len(amounts) == len(bodies)):
            raise ValueError("All lists (destinations, amounts, bodies) must be of the same length.")

        # Initialize state_inits if None
        if state_inits is None:
            state_inits = [None] * len(destinations)
        elif len(state_inits) != len(destinations):
            raise ValueError("Length of state_inits must match the length of destinations.")

        result_msgs = []
        for i in range(len(destinations)):
            destination = destinations[i]
            body = bodies[i] if bodies[i] is not None else Cell.empty()

            if isinstance(destination, str):
                destination = Address(destination)

            result_msgs.append(
                self.create_wallet_internal_message(destination=destination, value=amounts[i],
                                                    body=body, state_init=state_inits[i]))
        return await self.raw_transfer(msgs=result_msgs, query_id=query_id)

    async def send_init_external(self):
        if not self.state_init:
            raise ContractError('contract does not have state_init attribute')
        if 'private_key' not in self.__dict__:
            raise WalletError('must specify wallet private key!')
        body = self.raw_create_transfer_msg(private_key=self.private_key, wallet_id=self.wallet_id, messages=[self.create_wallet_internal_message(self.address)])
        return await self.send_external(state_init=self.state_init, body=body)

    @property
    def wallet_id(self) -> int:
        """
        :return: wallet_id taken from contract data
        """
        return HighloadWalletV3Data.deserialize(self.state.data.begin_parse()).wallet_id

    @property
    def last_clean_time(self) -> int:
        """
        :return: last_cleaned taken from contract data
        """
        return HighloadWalletV3Data.deserialize(self.state.data.begin_parse()).last_clean_time

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

    @property
    def queries(self) -> dict:
        """
        :return: queries taken from contract data
        """
        return HighloadWalletV3Data.deserialize(self.state.data.begin_parse()).queries

    async def get_last_clean_time(self):
        """
        :return: wallet's last_clean_time
        """
        return (await super().run_get_method(method='get_last_clean_time'))[0]

    async def get_timeout(self):
        """
        :return: wallet's timeout
        """
        return (await super().run_get_method(method='get_timeout'))[0]

    async def processed(self, query_id: int, need_clean: bool) -> bool:
        """
        :return: is query processed from wallet's get method
        """
        return (await super().run_get_method(method='processed?', stack=[query_id, -int(need_clean)]))[0]
