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
from pytoniq_core.tlb.utils import WalletV5WalletID
from pytoniq_core.tlb.custom.wallet import WalletV5R1Data, WalletMessage

WALLET_V5_R1_CODE = Cell.one_from_boc(
    b'\xb5\xee\x9cr\x01\x02\x14\x01\x00\x02\x81\x00\x01\x14\xff\x00\xf4\xa4\x13\xf4\xbc\xf2\xc8\x0b\x01\x02\x01 \x02\r\x02\x01H\x03\x04\x02\xdc\xd0 \xd7I\xc1 \x91[\x8fc \xd7\x0b\x1f \x82\x10extn\xbd!\x82\x10sint\xbd\xb0\x92_\x03\xe0\x82\x10extn\xba\x8e\xb4\x80 \xd7!\x01\xd0t\xd7!\xfa@0\xfaD\xf8(\xfaD0X\xbd\x91[\xe0\xedD\xd0\x81\x01A\xd7!\xf4\x05\x83\x07\xf4\x0eo\xa11\x910\xe1\x80@\xd7!p\x7f\xdb<\xe01 \xd7I\x81\x02\x80\xb9\x910\xe0p\xe2\x10\x0f\x02\x01 \x05\x0c\x02\x01 \x06\t\x02\x01n\x07\x08\x00\x19\xad\xcev\xa2h@ \xeb\x90\xeb\x85\xff\xc0\x00\x19\xaf\x1d\xf6\xa2h@\x10\xeb\x90\xeb\x85\x8f\xc0\x02\x01H\n\x0b\x00\x17\xb3%\xfbQ4\x1cu\xc8u\xc2\xc7\xe0\x00\x11\xb2b\xfbQ45\xc2\x80 \x00\x19\xbe_\x0fj&\x84\x08\n\x0e\xb9\x0f\xa0,\x01\x02\xf2\x0e\x01\x1e \xd7\x0b\x1f\x82\x10sign\xba\xf2\xe0\x8a\x7f\x0f\x01\xe6\x8e\xf0\xed\xa2\xed\xfb!\x83\x08\xd7"\x02\x83\x08\xd7# \x80 \xd7!\xd3\x1f\xd3\x1f\xd3\x1f\xedD\xd0\xd2\x00\xd3\x1f \xd3\x1f\xd3\xff\xd7\n\x00\n\xf9\x01@\xcc\xf9\x10\x9a(\x94_\n\xdb1\xe1\xf2\xc0\x87\xdf\x02\xb3P\x07\xb0\xf2\xd0\x84Q%\xba\xf2\xe0\x85P6\xba\xf2\xe0\x86\xf8#\xbb\xf2\xd0\x88"\x92\xf8\x00\xde\x01\xa4\x7f\xc8\xca\x00\xcb\x1f\x01\xcf\x16\xc9\xedT \x92\xf8\x0f\xdep\xdb<\xd8\x10\x03\xf6\xed\xa2\xed\xfb\x02\xf4\x04!n\x92l!\x8eL\x02!\xd790p\x94!\xc7\x00\xb3\x8e-\x01\xd7( v\x1eCl \xd7I\xc0\x08\xf2\xe0\x93 \xd7J\xc0\x02\xf2\xe0\x93 \xd7\x1d\x06\xc7\x12\xc2\x00R0\xb0\xf2\xd0\x89\xd7L\xd790\x01\xa4\xe8l\x12\x84\x07\xbb\xf2\xe0\x93\xd7J\xc0\x00\xf2\xe0\x93\xedU\xe2\xd2\x00\x01\xc0\x00\x91[\xe0\xeb\xd7,\x08\x14 \x91p\x96\x01\xd7,\x08\x1c\x12\xe2R\x10\xb1\xe3\x0f \xd7J\x11\x12\x13\x00\x96\x01\xfa@\x01\xfaD\xf8(\xfaD0X\xba\xf2\xe0\x91\xedD\xd0\x81\x01A\xd7\x18\xf4\x05\x04\x9d\x7f\xc8\xca\x00@\x04\x83\x07\xf4S\xf2\xe0\x8b\x8e\x14\x03\x83\x07\xf4[\xf2\xe0\x8c"\xd7\n\x00!n\x01\xb3\xb0\xf2\xd0\x90\xe2\xc8P\x03\xcf\x16\x12\xf4\x00\xc9\xedT\x00r0\xd7,\x08$\x8e-!\xf2\xe0\x92\xd2\x00\xedD\xd0\xd2\x00Q\x13\xba\xf2\xd0\x8fTP0\x911\x9c\x01\x81\x01@\xd7!\xd7\n\x00\xf2\xe0\x8e\xe2\xc8\xca\x00X\xcf\x16\xc9\xedT\x93\xf2\xc0\x8d\xe2\x00\x10\x93[\xdb1\xe1\xd7L\xd0')


class WalletV5R1(Wallet):

    @classmethod
    async def from_data(cls, provider: LiteClientLike, public_key: bytes, network_global_id: int, wc: int = 0,
                        wallet_id: typing.Optional[WalletV5WalletID] = None, **kwargs) -> "WalletV5R1":
        data = cls.create_data_cell(public_key, network_global_id, wallet_id, wc)
        return await super().from_code_and_data(provider, wc, WALLET_V5_R1_CODE, data, network_global_id=network_global_id, **kwargs)

    @staticmethod
    def create_data_cell(public_key: bytes, network_global_id: int, wallet_id: typing.Optional[WalletV5WalletID] = None, wc: typing.Optional[int] = 0,
                         is_signature_allowed: typing.Optional[bool] = True, extensions: typing.Optional[Cell] = None) -> Cell:
        if wallet_id is None:
            wallet_id = WalletV5WalletID(network_global_id=network_global_id, workchain=wc)
        return WalletV5R1Data(seqno=0, wallet_id=wallet_id, public_key=public_key, extensions=extensions, is_signature_allowed=is_signature_allowed).serialize()

    @classmethod
    async def from_private_key(cls, provider: LiteClientLike, private_key: bytes, network_global_id: int, wc: int = 0,
                               wallet_id: typing.Optional[WalletV5WalletID] = None):
        public_key = private_key_to_public_key(private_key)
        return await cls.from_data(provider=provider, public_key=public_key, network_global_id=network_global_id, wc=wc, wallet_id=wallet_id,
                                   private_key=private_key)

    @classmethod
    async def from_mnemonic(cls, provider: LiteClientLike, mnemonics: typing.Union[list, str], network_global_id: int, wc: int = 0,
                            wallet_id: typing.Optional[WalletV5WalletID] = None):
        if isinstance(mnemonics, str):
            mnemonics = mnemonics.split()
        assert mnemonic_is_valid(mnemonics), 'mnemonics are invalid!'
        _, private_key = mnemonic_to_private_key(mnemonics)
        return await cls.from_private_key(provider, private_key, network_global_id, wc, wallet_id)

    @classmethod
    async def create(cls, provider: LiteClientLike, network_global_id: int, wc: int = 0, wallet_id: typing.Optional[int] = None):
        mnemo = mnemonic_new(24)
        return mnemo, await cls.from_mnemonic(provider, mnemo, network_global_id, wc, wallet_id)

    @classmethod
    def pack_actions(cls, messages: typing.List[WalletMessage]) -> WalletMessage:
        actions_cell = Cell.empty()
        for msg in messages:
            action = Builder() \
                .store_uint(0x0ec3c86d, 32) \
                .store_uint(msg.send_mode, 8) \
                .store_ref(msg.message.serialize()) \
                .end_cell()
            actions_cell = Builder() \
                .store_ref(actions_cell) \
                .store_cell(action) \
                .end_cell()

        return Builder() \
            .store_uint(1, 1) \
            .store_ref(actions_cell) \
            .store_uint(0, 1) \
            .end_cell()

    def raw_create_transfer_msg(self, private_key: bytes, seqno: int, wallet_id: int, messages: typing.List[WalletMessage],
                                valid_until: typing.Optional[int] = None, op_code: typing.Optional[int] = None) -> Cell:
        assert len(messages) <= 255, 'For wallet v5, maximum messages amount is 255'

        if op_code is None:
            op_code = 0x7369676e  # signed external op code
        if valid_until is None:
            valid_until = int(time.time()) + 60

        signing_message = begin_cell().store_uint(op_code, 32)
        signing_message.store_uint(wallet_id, 32)
        if seqno == 0:
            signing_message.store_bits("1" * 32)
        else:
            if valid_until is not None:
                signing_message.store_uint(valid_until, 32)
            else:
                signing_message.store_uint(int(time.time()) + 60, 32)
        signing_message.store_uint(seqno, 32)
        signing_message.store_cell(self.pack_actions(messages))
        signing_message = signing_message.end_cell()
        signature = sign_message(signing_message.hash, private_key)

        return Builder() \
            .store_cell(signing_message) \
            .store_bytes(signature) \
            .end_cell()

    async def raw_transfer(self, msgs: typing.List[WalletMessage], seqno_from_get_meth: bool = True):
        if 'private_key' not in self.__dict__:
            raise WalletError('must specify wallet private key!')
        if seqno_from_get_meth:
            seqno = await self.get_seqno()
        else:
            seqno = self.seqno
        transfer_msg = self.raw_create_transfer_msg(private_key=self.private_key, seqno=seqno, wallet_id=self.wallet_id, messages=msgs)
        return await self.send_external(body=transfer_msg)

    async def transfer(self, destination: typing.Union[Address, str], amount: int, body: Cell = Cell.empty(),
                       state_init: StateInit = None):
        if isinstance(destination, str):
            destination = Address(destination)
        wallet_message = self.create_wallet_internal_message(destination=destination, value=amount, body=body, state_init=state_init)
        return await self.raw_transfer(msgs=[wallet_message])

    async def send_init_external(self):
        if not self.state_init:
            raise ContractError('contract does not have state_init attribute')
        if 'private_key' not in self.__dict__:
            raise WalletError('must specify wallet private key!')
        body = self.raw_create_transfer_msg(private_key=self.private_key, seqno=0, wallet_id=self.wallet_id, messages=[])
        return await self.send_external(state_init=self.state_init, body=body)

    @property
    def seqno(self) -> int:
        """
        :return: seqno taken from contract data
        """
        return WalletV5R1Data.deserialize(
            self.state.data.begin_parse(),
            self.network_global_id,
        ).seqno

    @property
    def wallet_id(self) -> int:
        """
        :return: wallet_id taken from contract data
        """
        return WalletV5R1Data.deserialize(
            self.state.data.begin_parse(),
            self.network_global_id,
        ).wallet_id.pack()

    @property
    def public_key(self) -> bytes:
        """
        :return: public_key taken from contract data
        """
        return WalletV5R1Data.deserialize(
            self.state.data.begin_parse(),
            self.network_global_id,
        ).public_key

    @property
    def extensions(self) -> Cell:
        """
        :return: extensions list taken from contract data
        """
        return WalletV5R1Data.deserialize(
            self.state.data.begin_parse(),
            self.network_global_id,
        ).extensions

    async def get_seqno(self):
        """
        :return: seqno from wallet's get method
        """
        return (await super().run_get_method("seqno"))[0]

    async def get_subwallet_id(self):
        """
        :return: subwallet_id from wallet's get method
        """
        return (await super().run_get_method("get_subwallet_id"))[0]

    async def get_extensions(self):
        """
        :return: extensions list from wallet's get method
        """
        return (await super().run_get_method("get_extensions"))[0]

    async def is_signature_allowed(self) -> bool:
        """
        :return: is signature allowed from wallet's get method
        """
        return (await super().run_get_method("is_signature_allowed"))[0]
