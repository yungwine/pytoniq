import time
import typing

from .wallet import WalletError, BaseWallet
from ...liteclient import LiteClientLike
from pytoniq_core.crypto.keys import private_key_to_public_key, mnemonic_to_private_key, mnemonic_is_valid, mnemonic_new
from pytoniq_core.crypto.signature import sign_message
from pytoniq_core.boc import Cell, Builder, begin_cell
from pytoniq_core.boc.address import Address
from pytoniq_core.tlb.account import StateInit
from pytoniq_core.tlb.custom.wallet import WalletV5R1Data, WalletMessage

WALLET_V5_R1_CODE = Cell.one_from_boc(
    b'\xb5\xee\x9crA\x02\x14\x01\x00\x02\x81\x00\x01\x14\xff\x00\xf4\xa4\x13\xf4\xbc\xf2\xc8\x0b\x01\x02\x01 \x02\r\x02\x01H\x03\x04\x02\xdc\xd0 \xd7I\xc1 \x91[\x8fc \xd7\x0b\x1f \x82\x10extn\xbd!\x82\x10sint\xbd\xb0\x92_\x03\xe0\x82\x10extn\xba\x8e\xb4\x80 \xd7!\x01\xd0t\xd7!\xfa@0\xfaD\xf8(\xfaD0X\xbd\x91[\xe0\xedD\xd0\x81\x01A\xd7!\xf4\x05\x83\x07\xf4\x0eo\xa11\x910\xe1\x80@\xd7!p\x7f\xdb<\xe01 \xd7I\x81\x02\x80\xb9\x910\xe0p\xe2\x10\x0f\x02\x01 \x05\x0c\x02\x01 \x06\t\x02\x01n\x07\x08\x00\x19\xad\xcev\xa2h@ \xeb\x90\xeb\x85\xff\xc0\x00\x19\xaf\x1d\xf6\xa2h@\x10\xeb\x90\xeb\x85\x8f\xc0\x02\x01H\n\x0b\x00\x17\xb3%\xfbQ4\x1cu\xc8u\xc2\xc7\xe0\x00\x11\xb2b\xfbQ45\xc2\x80 \x00\x19\xbe_\x0fj&\x84\x08\n\x0e\xb9\x0f\xa0,\x01\x02\xf2\x0e\x01\x1e \xd7\x0b\x1f\x82\x10sign\xba\xf2\xe0\x8a\x7f\x0f\x01\xe6\x8e\xf0\xed\xa2\xed\xfb!\x83\x08\xd7"\x02\x83\x08\xd7# \x80 \xd7!\xd3\x1f\xd3\x1f\xd3\x1f\xedD\xd0\xd2\x00\xd3\x1f \xd3\x1f\xd3\xff\xd7\n\x00\n\xf9\x01@\xcc\xf9\x10\x9a(\x94_\n\xdb1\xe1\xf2\xc0\x87\xdf\x02\xb3P\x07\xb0\xf2\xd0\x84Q%\xba\xf2\xe0\x85P6\xba\xf2\xe0\x86\xf8#\xbb\xf2\xd0\x88"\x92\xf8\x00\xde\x01\xa4\x7f\xc8\xca\x00\xcb\x1f\x01\xcf\x16\xc9\xedT \x92\xf8\x0f\xdep\xdb<\xd8\x10\x03\xf6\xed\xa2\xed\xfb\x02\xf4\x04!n\x92l!\x8eL\x02!\xd790p\x94!\xc7\x00\xb3\x8e-\x01\xd7( v\x1eCl \xd7I\xc0\x08\xf2\xe0\x93 \xd7J\xc0\x02\xf2\xe0\x93 \xd7\x1d\x06\xc7\x12\xc2\x00R0\xb0\xf2\xd0\x89\xd7L\xd790\x01\xa4\xe8l\x12\x84\x07\xbb\xf2\xe0\x93\xd7J\xc0\x00\xf2\xe0\x93\xedU\xe2\xd2\x00\x01\xc0\x00\x91[\xe0\xeb\xd7,\x08\x14 \x91p\x96\x01\xd7,\x08\x1c\x12\xe2R\x10\xb1\xe3\x0f \xd7J\x11\x12\x13\x00\x96\x01\xfa@\x01\xfaD\xf8(\xfaD0X\xba\xf2\xe0\x91\xedD\xd0\x81\x01A\xd7\x18\xf4\x05\x04\x9d\x7f\xc8\xca\x00@\x04\x83\x07\xf4S\xf2\xe0\x8b\x8e\x14\x03\x83\x07\xf4[\xf2\xe0\x8c"\xd7\n\x00!n\x01\xb3\xb0\xf2\xd0\x90\xe2\xc8P\x03\xcf\x16\x12\xf4\x00\xc9\xedT\x00r0\xd7,\x08$\x8e-!\xf2\xe0\x92\xd2\x00\xedD\xd0\xd2\x00Q\x13\xba\xf2\xd0\x8fTP0\x911\x9c\x01\x81\x01@\xd7!\xd7\n\x00\xf2\xe0\x8e\xe2\xc8\xca\x00X\xcf\x16\xc9\xedT\x93\xf2\xc0\x8d\xe2\x00\x10\x93[\xdb1\xe1\xd7L\xd0\xb4\xd6\xc3^')


class WalletV5WalletID:
    """
    wallet_id = network_global_id ^ context_id
    context_id_client$1 = wc:int8 version:uint8 counter:uint15
    context_id_backoffice$0 = counter:uint31
    """
    def __init__(self,
                 network_global_id: int,
                 workchain: int = None,
                 version: int = 0,
                 subwallet_number: int = 0,
                 context: int = None,
    ) -> None:
        """
        :param network_global_id: global id version taken from 19 config param. -239 for mainnet and -3 for testnet
        :param workchain: wallet's workchain (mostly -1 or 0)
        :param version: 8-bit uint, current v5r1 version is considered 0
        :param subwallet_number: any 15-bit uint, default is 0
        :param context: full custom wallet id, 31-bit uint
        """
        self.network_global_id = network_global_id
        self.subwallet_number = subwallet_number
        self.workchain = workchain
        self.version = version
        self.context = context
        if self.context is not None and not (0 <= self.context <= 0x7FFFFFFF):
            raise ValueError("context must be a 31-bit unsigned integer")

    def pack(self) -> int:
        if self.context is not None:
            return (self.context ^ self.network_global_id) & 0xFFFFFFFF
        ctx = 0
        ctx |= 1 << 31  # client context flag
        ctx |= (self.workchain & 0xFF) << 23
        ctx |= (self.version & 0xFF) << 15
        ctx |= self.subwallet_number & 0xFFFF
        return (ctx ^ self.network_global_id) & 0xFFFFFFFF

    @classmethod
    def unpack(
        cls,
        value: int,
        network_global_id: int,
    ) -> "WalletV5WalletID":
        ctx = (value ^ network_global_id) & 0xFFFFFFFF
        if not ctx & 0x80000000:
            return cls(context=ctx, network_global_id=network_global_id)
        subwallet_number = ctx & 0x7FFF
        version = (ctx >> 15) & 0xFF
        workchain = (ctx >> 23) & 0xFF
        if workchain & 0x80:  # wc uint -> int
            workchain -= 0x100

        return cls(
            subwallet_number=subwallet_number,
            workchain=workchain,
            version=version,
            network_global_id=network_global_id,
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}<{self.pack()!r}>"



class WalletV5R1(BaseWallet):

    @classmethod
    async def from_data(cls, provider: LiteClientLike, public_key: bytes, wc: int = 0,
                        wallet_id: typing.Union[WalletV5WalletID, int] = None, network_global_id: typing.Optional[int] = None,
                        subwallet_number: int = 0, is_signature_allowed: typing.Optional[bool] = True, **kwargs) -> "WalletV5R1":
        data = cls.create_data_cell(public_key, wc=wc, wallet_id=wallet_id, network_global_id=network_global_id, subwallet_number=subwallet_number, is_signature_allowed=is_signature_allowed)
        return await super().from_code_and_data(provider, wc, WALLET_V5_R1_CODE, data, **kwargs)

    @staticmethod
    def create_data_cell(public_key: bytes, wc: typing.Optional[int] = 0,
                         wallet_id: typing.Union[WalletV5WalletID, int] = None,
                         network_global_id: typing.Optional[int] = None,
                         subwallet_number: int = 0, is_signature_allowed: bool = True,
                         extensions: typing.Optional[Cell] = None) -> Cell:
        if wallet_id is None and network_global_id is None:
            raise WalletError("provide either wallet_id or network_global_id param")
        if wallet_id is None:
            wallet_id = WalletV5WalletID(workchain=wc, subwallet_number=subwallet_number, network_global_id=network_global_id).pack()
        return WalletV5R1Data(seqno=0, wallet_id=wallet_id, public_key=public_key, extensions=extensions, is_signature_allowed=is_signature_allowed).serialize()

    @classmethod
    async def from_private_key(cls, provider: LiteClientLike, private_key: bytes, wc: int = 0,
                               wallet_id: typing.Union[WalletV5WalletID, int] = None,
                               network_global_id: typing.Optional[int] = None,
                               subwallet_number: int = 0, is_signature_allowed: bool = True):
        public_key = private_key_to_public_key(private_key)
        return await cls.from_data(provider=provider, public_key=public_key, network_global_id=network_global_id, wc=wc, wallet_id=wallet_id,
                                   private_key=private_key, subwallet_number=subwallet_number, is_signature_allowed=is_signature_allowed)

    @classmethod
    async def from_mnemonic(cls, provider: LiteClientLike, mnemonics: typing.Union[list, str], wc: int = 0,
                            wallet_id: typing.Union[WalletV5WalletID, int] = None,
                            network_global_id: typing.Optional[int] = None,
                            subwallet_number: int = 0, is_signature_allowed: bool = True):
        if isinstance(mnemonics, str):
            mnemonics = mnemonics.split()
        assert mnemonic_is_valid(mnemonics), 'mnemonics are invalid!'
        _, private_key = mnemonic_to_private_key(mnemonics)
        return await cls.from_private_key(provider, private_key=private_key, wc=wc, wallet_id=wallet_id,
                                          network_global_id=network_global_id, subwallet_number=subwallet_number,
                                          is_signature_allowed=is_signature_allowed)

    @classmethod
    async def create(cls, provider: LiteClientLike, wc: int = 0, wallet_id: typing.Optional[int] = None,
                     network_global_id: typing.Optional[int] = None,
                     subwallet_number: int = 0, is_signature_allowed: bool = True):
        mnemo = mnemonic_new(24)
        return mnemo, await cls.from_mnemonic(provider, mnemonics=mnemo, wc=wc, wallet_id=wallet_id,
                                              network_global_id=network_global_id, subwallet_number=subwallet_number,
                                              is_signature_allowed=is_signature_allowed)

    @classmethod
    def pack_actions(cls, messages: typing.List[WalletMessage]) -> Cell:
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
                                valid_until: typing.Optional[int] = None) -> Cell:
        assert len(messages) <= 255, 'For wallet v5, maximum messages amount is 255'

        op_code = 0x7369676e  # signed external op code

        signing_message = begin_cell().store_uint(op_code, 32)
        signing_message.store_uint(wallet_id, 32)
        if seqno == 0:
            signing_message.store_uint(2**32 - 1, 32)
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

    async def transfer(self, destination: typing.Union[Address, str], amount: int, body: Cell = Cell.empty(),
                       state_init: StateInit = None):
        if isinstance(destination, str):
            destination = Address(destination)
        wallet_message = self.create_wallet_internal_message(destination=destination, value=amount, body=body, state_init=state_init)
        return await self.raw_transfer(msgs=[wallet_message])

    @property
    def seqno(self) -> int:
        """
        :return: seqno taken from contract data
        """
        return WalletV5R1Data.deserialize(
            self.state.data.begin_parse(),
        ).seqno

    @property
    def wallet_id(self) -> int:
        """
        :return: wallet_id taken from contract data
        """
        return WalletV5R1Data.deserialize(
            self.state.data.begin_parse(),
        ).wallet_id

    def unpacked_wallet_id(self, network_global_id: int) -> WalletV5WalletID:
        """
        :param network_global_id: network global id taken from blockchain's config #19. -239 for mainnet, -3 for testnet
        :return: unpacked wallet_id taken from contract data
        """
        return WalletV5WalletID.unpack(WalletV5R1Data.deserialize(
            self.state.data.begin_parse()
        ).wallet_id, network_global_id)

    @property
    def public_key(self) -> bytes:
        """
        :return: public_key taken from contract data
        """
        return WalletV5R1Data.deserialize(
            self.state.data.begin_parse(),
        ).public_key

    @property
    def extensions(self) -> Cell:
        """
        :return: extensions list taken from contract data
        """
        return WalletV5R1Data.deserialize(
            self.state.data.begin_parse(),
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

    async def get_unpacked_wallet_id(self, network_global_id: int):
        """
        :return: unpacked subwallet_id from wallet's get method
        """
        wallet_id = (await super().run_get_method("get_subwallet_id"))[0]
        return WalletV5WalletID.unpack(wallet_id, network_global_id)


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
