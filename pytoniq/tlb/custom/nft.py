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


class NftItemSaleFees(TlbScheme):
    """
    nft_item_sale_fees#_ marketplace_fee_address:Address marketplace_fee:Grams royalty_address:Address royalty_amount:Grams = NftItemSaleFees;
    """
    def __init__(self,
                 marketplace_fee_address: typing.Optional[Address] = None,
                 marketplace_fee: typing.Optional[int] = None,
                 royalty_address: typing.Optional[Address] = None,
                 royalty_amount: typing.Optional[int] = None
                 ):
        self.marketplace_fee_address = marketplace_fee_address
        self.marketplace_fee = marketplace_fee
        self.royalty_address = royalty_address
        self.royalty_amount = royalty_amount

    def serialize(self):
        return Builder()\
            .store_address(self.marketplace_fee_address)\
            .store_coins(self.marketplace_fee)\
            .store_address(self.royalty_address)\
            .store_coins(self.royalty_amount)\
            .end_cell()

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        return cls(
            marketplace_fee_address=cell_slice.load_address(),
            marketplace_fee=cell_slice.load_coins(),
            royalty_address=cell_slice.load_address(),
            royalty_amount=cell_slice.load_coins()
        )


class NftItemSaleData(TlbScheme):
    """
    nft_item_sale_data#_ is_complete:bool created_at:uint32 marketplace_address:Address nft_address:Address nft_owner_address:Address full_price:grams fees_cell:^NftItemSaleFees can_deploy_by_external:bool = NftItemSaleData;
    """
    def __init__(self,
                 is_complete: typing.Optional[bool] = None,
                 created_at: typing.Optional[int] = None,
                 marketplace_address: typing.Optional[Address] = None,
                 nft_address: typing.Optional[Address] = None,
                 nft_owner_address: typing.Optional[Address] = None,
                 full_price: typing.Optional[int] = None,
                 fees_cell: typing.Optional[NftItemSaleFees] = None,
                 can_deploy_by_external: typing.Optional[bool] = None,
                 ):
        self.is_complete = is_complete
        self.created_at = created_at
        if isinstance(marketplace_address, str):
            marketplace_address = Address(marketplace_address)
        if isinstance(nft_address, str):
            nft_address = Address(nft_address)
        if isinstance(nft_owner_address, str):
            nft_owner_address = Address(nft_owner_address)
        self.marketplace_address = marketplace_address
        self.nft_address = nft_address
        self.nft_owner_address = nft_owner_address
        self.full_price = full_price
        self.fees_cell = fees_cell
        self.can_deploy_by_external = can_deploy_by_external

    def serialize(self) -> Cell:
        builder = Builder()
        builder\
            .store_bool(self.is_complete)\
            .store_uint(self.created_at, 32)\
            .store_address(self.marketplace_address)\
            .store_address(self.nft_address)\
            .store_address(self.nft_owner_address)\
            .store_coins(self.full_price)\
            .store_ref(self.fees_cell.serialize())\
            .store_bool(self.can_deploy_by_external)
        return builder.end_cell()

    @classmethod
    def deserialize(cls, cell_slice: Slice) -> "NftItemSaleData":
        return cls(
            is_complete=cell_slice.load_bool(),
            created_at=cell_slice.load_uint(32),
            marketplace_address=cell_slice.load_address(),
            nft_address=cell_slice.load_address(),
            nft_owner_address=cell_slice.load_address(),
            full_price=cell_slice.load_coins(),
            fees_cell=NftItemSaleFees.deserialize(cell_slice.load_ref().begin_parse()),
            can_deploy_by_external=cell_slice.load_bool()
        )


