import typing

from ..tlb import TlbScheme
from ...boc import Cell, Builder, Slice, HashMap, Address


class NftItemData(TlbScheme):
    """
    nft_item_data#_ index:uint64 collection_address:Address owner_address:Address content:^Cell = NftItemData;
    """
    def __init__(self,
                 index: typing.Optional[int] = 0,
                 collection_address: typing.Optional[Address] = None,
                 owner_address: typing.Optional[Address] = None,
                 content: typing.Optional[Cell] = None
                 ):
        self.index = index
        if isinstance(collection_address, str):
            collection_address = Address(collection_address)
        if isinstance(owner_address, str):
            collection_address = Address(collection_address)
        self.collection_address = collection_address
        self.owner_address = owner_address
        self.content = content

    def serialize(self) -> Cell:
        builder = Builder()
        builder\
            .store_uint(self.index, 64)\
            .store_address(self.collection_address)\
            .store_address(self.owner_address)\
            .store_ref(self.content)
        return builder.end_cell()

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(index=cell_slice.load_uint(64), collection_address=cell_slice.load_address(), owner_address=cell_slice.load_address(), content=cell_slice.load_ref())


