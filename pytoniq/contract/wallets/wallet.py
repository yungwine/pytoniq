import time
import typing

from ...liteclient.client import LiteClient
from ..contract import Contract, ContractError
from ...crypto.keys import private_key_to_public_key, mnemonic_to_private_key, mnemonic_is_valid, mnemonic_new
from ...crypto.signature import sign_message
from ...boc import Cell, Builder
from ...boc.address import Address
from ...tlb.account import StateInit
from ...tlb.custom.wallet import WalletV3Data, WalletV4Data, WalletMessage

WALLET_V3_R2_CODE = Cell.one_from_boc(
    b'\xb5\xee\x9crA\x01\x01\x01\x00q\x00\x00\xde\xff\x00 \xdd \x82\x01L\x97\xba!\x82\x013\x9c\xba\xb1\x9fq\xb0\xedD\xd0\xd3\x1f\xd3\x1f1\xd7\x0b\xff\xe3\x04\xe0\xa4\xf2`\x83\x08\xd7\x18 \xd3\x1f\xd3\x1f\xd3\x1f\xf8#\x13\xbb\xf2c\xedD\xd0\xd3\x1f\xd3\x1f\xd3\xff\xd1Q2\xba\xf2\xa1QD\xba\xf2\xa2\x04\xf9\x01T\x10U\xf9\x10\xf2\xa3\xf8\x00\x93 \xd7J\x96\xd3\x07\xd4\x02\xfb\x00\xe8\xd1\x01\xa4\xc8\xcb\x1f\xcb\x1f\xcb\xff\xc9\xedT\x10\xbdm\xad')
WALLET_V3_R1_CODE = Cell.one_from_boc(
    b'\xb5\xee\x9crA\x01\x01\x01\x00b\x00\x00\xc0\xff\x00 \xdd \x82\x01L\x97\xba\x970\xedD\xd0\xd7\x0b\x1f\xe0\xa4\xf2`\x83\x08\xd7\x18 \xd3\x1f\xd3\x1f\xd3\x1f\xf8#\x13\xbb\xf2c\xedD\xd0\xd3\x1f\xd3\x1f\xd3\xff\xd1Q2\xba\xf2\xa1QD\xba\xf2\xa2\x04\xf9\x01T\x10U\xf9\x10\xf2\xa3\xf8\x00\x93 \xd7J\x96\xd3\x07\xd4\x02\xfb\x00\xe8\xd1\x01\xa4\xc8\xcb\x1f\xcb\x1f\xcb\xff\xc9\xedT?\xben\xe0')
WALLET_V4_R2_CODE = Cell.one_from_boc(
    b'\xb5\xee\x9crA\x02\x14\x01\x00\x02\xd4\x00\x01\x14\xff\x00\xf4\xa4\x13\xf4\xbc\xf2\xc8\x0b\x01\x02\x01 \x02\x03\x02\x01H\x04\x05\x04\xf8\xf2\x83\x08\xd7\x18 \xd3\x1f\xd3\x1f\xd3\x1f\x02\xf8#\xbb\xf2d\xedD\xd0\xd3\x1f\xd3\x1f\xd3\xff\xf4\x04\xd1QC\xba\xf2\xa1QQ\xba\xf2\xa2\x05\xf9\x01T\x10d\xf9\x10\xf2\xa3\xf8\x00$\xa4\xc8\xcb\x1fR@\xcb\x1fR0\xcb\xffR\x10\xf4\x00\xc9\xedT\xf8\x0f\x01\xd3\x07!\xc0\x00\x9flQ\x93 \xd7J\x96\xd3\x07\xd4\x02\xfb\x00\xe80\xe0!\xc0\x01\xe3\x00!\xc0\x02\xe3\x00\x01\xc0\x03\x910\xe3\r\x03\xa4\xc8\xcb\x1f\x12\xcb\x1f\xcb\xff\x10\x11\x12\x13\x02\xe6\xd0\x01\xd0\xd3\x03!q\xb0\x92_\x04\xe0"\xd7I\xc1 \x92_\x04\xe0\x02\xd3\x1f!\x82\x10plug\xbd"\x82\x10dstr\xbd\xb0\x92_\x05\xe0\x03\xfa@0 \xfaD\x01\xc8\xca\x07\xcb\xff\xc9\xd0\xedD\xd0\x81\x01@\xd7!\xf4\x040\\\x81\x01\x08\xf4\no\xa11\xb3\x92_\x07\xe0\x05\xd3?\xc8%\x82\x10plug\xba\x9280\xe3\r\x03\x82\x10dstr\xba\x92_\x06\xe3\r\x06\x07\x02\x01 \x08\t\x00x\x01\xfa\x00\xf4\x040\xf8\'o"0P\n\xa1!\xbe\xf2\xe0P\x82\x10plug\x83\x1e\xb1p\x80\x18P\x04\xcb\x05&\xcf\x16X\xfa\x02\x19\xf4\x00\xcbi\x17\xcb\x1fR`\xcb? \xc9\x80@\xfb\x00\x06\x00\x8aP\x04\x81\x01\x08\xf4Y0\xedD\xd0\x81\x01@\xd7 \xc8\x01\xcf\x16\xf4\x00\xc9\xedT\x01r\xb0\x8e#\x82\x10dstr\x83\x1e\xb1p\x80\x18P\x05\xcb\x05P\x03\xcf\x16#\xfa\x02\x13\xcbj\xcb\x1f\xcb?\xc9\x80@\xfb\x00\x92_\x03\xe2\x02\x01 \n\x0b\x00Y\xbd$+oj&\x84\x08\n\x06\xb9\x0f\xa0!\x84p\xd4\x08\x08G\xa4\x93})\x91\x0c\xe6\x90>\x9f\xf9\x83x\x12\x80\x1bx\x10\x14\x89\x87\x15\x9f1\x84\x02\x01X\x0c\r\x00\x11\xb8\xc9~\xd4M\rp\xb1\xf8\x00=\xb2\x9d\xfbQ4 @P5\xc8}\x01\x0c\x00\xb22\x81\xf2\xff\xf2t\x00`@B=\x02\x9b\xe8L`\x02\x01 \x0e\x0f\x00\x19\xad\xcev\xa2h@ k\x90\xeb\x85\xff\xc0\x00\x19\xaf\x1d\xf6\xa2h@\x10k\x90\xeb\x85\x8f\xc0\x00n\xd2\x07\xfa\x00\xd4\xd4"\xf9\x00\x05\xc8\xca\x07\x15\xcb\xff\xc9\xd0wt\x80\x18\xc8\xcb\x05\xcb\x02"\xcf\x16P\x05\xfa\x02\x14\xcbk\x12\xcc\xcc\xc9s\xfb\x00\xc8@\x14\x81\x01\x08\xf4Q\xf2\xa7\x02\x00p\x81\x01\x08\xd7\x18\xfa\x00\xd3?\xc8T G\x81\x01\x08\xf4Q\xf2\xa7\x82\x10notept\x80\x18\xc8\xcb\x05\xcb\x02P\x06\xcf\x16P\x04\xfa\x02\x14\xcbj\x12\xcb\x1f\xcb?\xc9s\xfb\x00\x02\x00l\x81\x01\x08\xd7\x18\xfa\x00\xd3?0R$\x81\x01\x08\xf4Y\xf2\xa7\x82\x10dstrpt\x80\x18\xc8\xcb\x05\xcb\x02P\x05\xcf\x16P\x03\xfa\x02\x13\xcbj\xcb\x1f\x12\xcb?\xc9s\xfb\x00\x00\n\xf4\x00\xc9\xedTib%\xe5')


class WalletError(ContractError):
    pass


class Wallet(Contract):
    @classmethod
    async def from_private_key(cls, *args, **kwargs): ...

    @staticmethod
    def raw_create_transfer_msg(*args, **kwargs): ...

    @classmethod
    async def from_mnemonic(cls, *args, **kwargs): ...

    @classmethod
    async def create(cls, *args, **kwargs): ...

    @staticmethod
    def create_wallet_internal_message(destination: Address, send_mode: int = 3, value: int = 0, body: typing.Union[Cell, str] = None,
                                       state_init: typing.Optional[StateInit] = None, **kwargs) -> WalletMessage:
        if isinstance(body, str):
            body = Builder()\
                .store_uint(0, 32)\
                .store_string(body)\
                .end_cell()

        message = Contract.create_internal_msg(dest=destination, value=value, body=body, state_init=state_init, **kwargs)
        return WalletMessage(send_mode=send_mode, message=message)

    async def send_init_external(self): ...

    async def raw_transfer(self, *args, **kwargs): ...

    async def transfer(self, *args, **kwargs): ...


class BaseWallet(Wallet):
    """
    class for user wallets such as v4r2, v3r2, etc.
    """

    @classmethod
    async def from_private_key(cls, provider: LiteClient, private_key: bytes, wc: int = 0,
                               wallet_id: typing.Optional[int] = None, version: str = 'v3r2'):
        public_key = private_key_to_public_key(private_key)
        if version == 'v3r2':
            return await WalletV3R2.from_data(provider=provider, wc=wc, public_key=public_key, wallet_id=wallet_id,
                                              private_key=private_key)
        elif version == 'v4r2':
            return await WalletV4R2.from_data(provider=provider, wc=wc, public_key=public_key, wallet_id=wallet_id,
                                              private_key=private_key)
        elif version == 'v3r1':
            return await WalletV3R1.from_data(provider=provider, wc=wc, public_key=public_key, wallet_id=wallet_id,
                                              private_key=private_key)
        else:
            raise Exception(f'Wallet version {version} does not supported')

    @classmethod
    async def from_mnemonic(cls, provider: LiteClient, mnemonics: typing.Union[list, str], wc: int = 0,
                            wallet_id: typing.Optional[int] = None, version: str = 'v3r2'):
        if isinstance(mnemonics, str):
            mnemonics = mnemonics.split()
        assert mnemonic_is_valid(mnemonics), 'mnemonics are invalid!'
        _, private_key = mnemonic_to_private_key(mnemonics)
        return await cls.from_private_key(provider, private_key, wc, wallet_id, version)

    @classmethod
    async def create(cls, provider: LiteClient, wc: int = 0, wallet_id: typing.Optional[int] = None,
                     version: str = 'v3r2'):
        """
        :param provider: provider
        :param wc: wallet workchain
        :param wallet_id: subwallet_id
        :param version: wallet version
        :return: mnemonics and Wallet instance of provided version
        """
        mnemo = mnemonic_new(24)
        return mnemo, await cls.from_mnemonic(provider, mnemo, wc, wallet_id, version)

    @staticmethod
    def raw_create_transfer_msg(private_key: bytes, seqno: int, wallet_id: int, messages: typing.List[WalletMessage],
                                valid_until: typing.Optional[int] = None) -> Cell:
        signing_message = Builder().store_uint(wallet_id, 32)
        if seqno == 0:
            signing_message.store_bits('1' * 32)  # bin(2**32 - 1)
        else:
            if valid_until is not None:
                signing_message.store_uint(valid_until, 32)
            else:
                signing_message.store_uint(int(time.time()) + 60, 32)
        signing_message.store_uint(seqno, 32)
        for m in messages:
            signing_message.store_cell(m.serialize())
        signing_message = signing_message.end_cell()
        signature = sign_message(signing_message.hash, private_key)
        return Builder() \
            .store_bytes(signature) \
            .store_cell(signing_message) \
            .end_cell()

    async def raw_transfer(self, msgs: typing.List[WalletMessage], seqno_from_get_meth: bool = True):
        """
        :param msgs: list of WalletMessages. to create one call create_wallet_internal_message meth
        :param seqno_from_get_meth: if True LiteClient will request seqno get method and use it, otherwise seqno from contract data will be taken
        """
        assert len(msgs) <= 4, 'for common wallet maximum messages amount is 4'
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

    async def get_seqno(self) -> int:
        """
        :return: seqno from wallet's get method
        """
        return (await super().run_get_method('seqno'))[0]

    async def get_public_key(self) -> int:
        """
        :return: public key from wallet's get method
        """
        if self.__class__ == WalletV3R1:
            raise Exception('WalletV3R1 doesn\'t have get_public_key get method. Use .public_key attribute')
        return (await super().run_get_method('get_public_key'))[0]

    async def deploy_via_internal(self, contract: Contract, deploy_amount: int = int(0.05 * 10**9)):
        return await self.transfer(destination=contract.address, amount=deploy_amount, state_init=contract.state_init)


class WalletV3(BaseWallet):

    @classmethod
    async def from_code_and_data(cls, provider: LiteClient, code: Cell, public_key: bytes, wc: int = 0,
                                 wallet_id: typing.Optional[int] = None, private_key: typing.Optional[bytes] = None):
        data = cls.create_data_cell(public_key, wallet_id, wc)
        return await super().from_code_and_data(provider, wc, code, data, private_key=private_key)

    @staticmethod
    def create_data_cell(public_key: bytes, wallet_id: typing.Optional[int] = None,
                         wc: typing.Optional[int] = 0) -> Cell:
        if wallet_id is None:
            wallet_id = 698983191 + wc
        return WalletV3Data(seqno=0, wallet_id=wallet_id, public_key=public_key).serialize()

    @property
    def seqno(self) -> int:
        """
        :return: seqno taken from contract data
        """
        return WalletV3Data.deserialize(self.state.data.begin_parse()).seqno

    @property
    def wallet_id(self) -> int:
        """
        :return: wallet_id taken from contract data
        """
        return WalletV3Data.deserialize(self.state.data.begin_parse()).wallet_id

    @property
    def public_key(self) -> bytes:
        """
        :return: public_key taken from contract data
        """
        return WalletV3Data.deserialize(self.state.data.begin_parse()).public_key


class WalletV4(BaseWallet):

    @classmethod
    async def from_code_and_data(cls, provider: LiteClient, code: Cell, public_key: bytes, wc: int = 0,
                                 wallet_id: typing.Optional[int] = None, **kwargs):
        data = cls.create_data_cell(public_key, wallet_id, wc)
        return await super().from_code_and_data(provider, wc, code, data, **kwargs)

    @staticmethod
    def create_data_cell(public_key: bytes, wallet_id: typing.Optional[int] = None, wc: typing.Optional[int] = 0,
                         plugins: typing.Optional[Cell] = None) -> Cell:
        if wallet_id is None:
            wallet_id = 698983191 + wc
        return WalletV4Data(seqno=0, wallet_id=wallet_id, public_key=public_key, plugins=plugins).serialize()

    @staticmethod
    def raw_create_transfer_msg(private_key: bytes, seqno: int, wallet_id: int, messages: typing.List[WalletMessage],
                                valid_until: typing.Optional[int] = None, op_code: int = 0) -> Cell:
        signing_message = Builder().store_uint(wallet_id, 32)
        if seqno == 0:
            signing_message.store_bits('1' * 32)  # bin(2**32 - 1)
        else:
            if valid_until is not None:
                signing_message.store_uint(valid_until, 32)
            else:
                signing_message.store_uint(int(time.time()) + 60, 32)
        signing_message.store_uint(seqno, 32)
        signing_message.store_uint(op_code, 32)
        for m in messages:
            signing_message.store_cell(m.serialize())
        signing_message = signing_message.end_cell()
        signature = sign_message(signing_message.hash, private_key)
        return Builder() \
            .store_bytes(signature) \
            .store_cell(signing_message) \
            .end_cell()

    @property
    def seqno(self) -> int:
        """
        :return: seqno taken from contract data
        """
        return WalletV4Data.deserialize(self.state.data.begin_parse()).seqno

    @property
    def wallet_id(self) -> int:
        """
        :return: wallet_id taken from contract data
        """
        return WalletV4Data.deserialize(self.state.data.begin_parse()).wallet_id

    @property
    def public_key(self) -> bytes:
        """
        :return: public_key taken from contract data
        """
        return WalletV4Data.deserialize(self.state.data.begin_parse()).public_key

    @property
    def plugins(self) -> Cell:
        return WalletV4Data.deserialize(self.state.data.begin_parse()).plugins

    async def get_plugin_list(self):
        """
        :return: plugins list from wallet's get method
        """
        return (await super().run_get_method(method='get_plugin_list', stack=[]))[0]

    async def is_plugin_installed(self, address: Address) -> bool:
        """
        :return: is plugin installed from wallet's get method
        """
        return bool((await super().run_get_method(method='is_plugin_installed', stack=[address.wc, address.hash_part]))[0])


class WalletV3R1(WalletV3):

    @classmethod
    async def from_data(cls, provider: LiteClient, public_key: bytes, wc: int = 0,
                        wallet_id: typing.Optional[int] = None, **kwargs):
        return await super().from_code_and_data(provider=provider, code=WALLET_V3_R1_CODE, public_key=public_key, wc=wc,
                                                wallet_id=wallet_id, **kwargs)

    @classmethod
    async def from_mnemonic(cls, provider: LiteClient, mnemonics: typing.Union[list, str], wc: int = 0,
                            wallet_id: typing.Optional[int] = None):
        if isinstance(mnemonics, str):
            mnemonics = mnemonics.split()
        assert mnemonic_is_valid(mnemonics), 'mnemonics are invalid!'
        _, private_key = mnemonic_to_private_key(mnemonics)
        return await super().from_private_key(provider, private_key, wc, wallet_id, 'v3r1')

    @classmethod
    async def create(cls, provider: LiteClient, wc: int = 0, wallet_id: typing.Optional[int] = None):
        """
        :param provider: provider
        :param wc: wallet workchain
        :param wallet_id: subwallet_id
        :return: mnemonics and Wallet instance of provided version
        """
        return super().create(provider=provider, wc=wc, wallet_id=wallet_id, version='v3r1')


class WalletV3R2(WalletV3):

    @classmethod
    async def from_data(cls, provider: LiteClient, public_key: bytes, wc: int = 0,
                        wallet_id: typing.Optional[int] = None, **kwargs):
        return await super().from_code_and_data(provider=provider, code=WALLET_V3_R2_CODE, public_key=public_key, wc=wc,
                                                wallet_id=wallet_id, **kwargs)

    @classmethod
    async def from_mnemonic(cls, provider: LiteClient, mnemonics: typing.Union[list, str], wc: int = 0,
                            wallet_id: typing.Optional[int] = None):
        if isinstance(mnemonics, str):
            mnemonics = mnemonics.split()
        assert mnemonic_is_valid(mnemonics), 'mnemonics are invalid!'
        _, private_key = mnemonic_to_private_key(mnemonics)
        return await super().from_private_key(provider, private_key, wc, wallet_id, 'v3r2')

    @classmethod
    async def create(cls, provider: LiteClient, wc: int = 0, wallet_id: typing.Optional[int] = None):
        """
        :param provider: provider
        :param wc: wallet workchain
        :param wallet_id: subwallet_id
        :return: mnemonics and Wallet instance of provided version
        """
        return super().create(provider=provider, wc=wc, wallet_id=wallet_id, version='v3r2')


class WalletV4R2(WalletV4):

    @classmethod
    async def from_data(cls, provider: LiteClient, public_key: bytes, wc: int = 0,
                        wallet_id: typing.Optional[int] = None, **kwargs):
        return await super().from_code_and_data(provider=provider, code=WALLET_V4_R2_CODE, public_key=public_key, wc=wc,
                                                wallet_id=wallet_id, **kwargs)

    @classmethod
    async def from_mnemonic(cls, provider: LiteClient, mnemonics: typing.Union[list, str], wc: int = 0,
                            wallet_id: typing.Optional[int] = None):
        if isinstance(mnemonics, str):
            mnemonics = mnemonics.split()
        assert mnemonic_is_valid(mnemonics), 'mnemonics are invalid!'
        _, private_key = mnemonic_to_private_key(mnemonics)
        return await super().from_private_key(provider, private_key, wc, wallet_id, 'v4r2')

    @classmethod
    async def create(cls, provider: LiteClient, wc: int = 0, wallet_id: typing.Optional[int] = None):
        """
        :param provider: provider
        :param wc: wallet workchain
        :param wallet_id: subwallet_id
        :return: mnemonics and Wallet instance of provided version
        """
        return super().create(provider=provider, wc=wc, wallet_id=wallet_id, version='v4r2')
