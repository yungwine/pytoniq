import typing

from ..tlb import TlbScheme
from ..transaction import MessageAny
from ...boc import Cell, Builder, Slice


class WalletV3Data(TlbScheme):
    """
    wallet_v3_data#_ seqno:uint32 wallet_id:uint32 public_key:bits256 = WalletV3Data;
    """
    def __init__(self,
                 seqno: typing.Optional[int] = 0,
                 wallet_id: typing.Optional[int] = None,
                 public_key: typing.Optional[bytes] = None
                 ):
        self.seqno = seqno
        if wallet_id is None:
            wallet_id = 698983191
        self.wallet_id = wallet_id
        if public_key is None:
            raise Exception('Public Key required for Wallet!')
        self.public_key = public_key

    def serialize(self) -> Cell:
        builder = Builder()
        builder\
            .store_uint(self.seqno, 32)\
            .store_uint(self.wallet_id, 32)\
            .store_bytes(self.public_key)
        return builder.end_cell()

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(seqno=cell_slice.load_uint(32), wallet_id=cell_slice.load_uint(32), public_key=cell_slice.load_bytes(32))


class WalletV4Data(TlbScheme):
    """
    // wc_n_address#_ wc:int8 addr_hash:uint256 = WcAndAddress;
    wallet_v4_data#_ seqno:uint32 wallet_id:uint32 public_key:bits256 plugins:(Maybe ^Cell) = WalletV4Data;
    """
    def __init__(self,
                 seqno: typing.Optional[int] = 0,
                 wallet_id: typing.Optional[int] = None,
                 public_key: typing.Optional[bytes] = None,
                 plugins: typing.Optional[Cell] = None
                 ):
        self.seqno = seqno
        if wallet_id is None:
            wallet_id = 698983191
        self.wallet_id = wallet_id
        if public_key is None:
            raise Exception('Public Key required for Wallet!')
        self.public_key = public_key
        self.plugins = plugins

    def serialize(self) -> Cell:
        builder = Builder()
        builder\
            .store_uint(self.seqno, 32)\
            .store_uint(self.wallet_id, 32)\
            .store_bytes(self.public_key)\
            .store_dict(self.plugins)
        return builder.end_cell()

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(seqno=cell_slice.load_uint(32), wallet_id=cell_slice.load_uint(32), public_key=cell_slice.load_bytes(32), plugins=cell_slice.load_maybe_ref())


class WalletMessage(TlbScheme):
    """
    wallet_message$_ send_mode:uint8 message:^MessageAny = WalletMessage;
    """

    def __init__(self, send_mode: int, message: MessageAny):
        self.send_mode = send_mode
        self.message = message

    def serialize(self):
        builder = Builder()
        builder.store_uint(self.send_mode, 8)
        builder.store_ref(self.message.serialize())
        return builder.end_cell()

    @classmethod
    def deserialize(cls, *args):
        pass




