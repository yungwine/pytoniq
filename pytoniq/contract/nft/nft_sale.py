import time
import typing

from ..contract import Contract, ContractError
from ...liteclient.client import LiteClient
from pytoniq_core.boc import Cell, Builder, HashMap
from pytoniq_core.boc.address import Address
from pytoniq_core.tlb.custom.nft import NftItemSaleData, NftItemSaleFees


# https://github.com/getgems-io/nft-contracts/blob/main/packages/contracts/sources/nft-fixprice-sale-v3r2.fc
NFT_SALE_CODE = Cell.one_from_boc(b"\xb5\xee\x9crA\x02\x0b\x01\x00\x02\xb9\x00\x01\x14\xff\x00\xf4\xa4\x13\xf4\xbc\xf2\xc8\x0b\x01\x02\x01 \x02\x03\x02\x01H\x04\x05\x00~\xf20\xedD\xd0\xd3\x00\xd3\x1f\xfa@\xfa@\xfa@\xfa\x00\xd4\xd3\x000\xc0\x01\x8e\x1d\xf8\x00p\x07\xc8\xcb\x00\x16\xcb\x1fP\x04\xcf\x16X\xcf\x16\x01\xcf\x16\x01\xfa\x02\xcc\xcb\x00\xc9\xedT\xe0_\x07\x82\x00\xff\xfe\xf2\xf0\x02\x02\xcd\x06\x07\x00W\xa08Y\xda\x89\xa1\xa6\x01\xa6?\xf4\x81\xf4\x81\xf4\x81\xf4\x01\xa9\xa6\x00`a\xa1\xf4\x81\xf4\x01\xf4\x81\xf4\x00a\x04 \x8c\x92\xb0\xa0\x15\x80\x02\xab\x01\x01\xf7\xd0\x0e\x86\x98\x18\x0b\x8d\x84\x92\xf8'\x07\xd2\x01\x87j&\x86\x98\x06\x98\xff\xd2\x07\xd2\x07\xd2\x07\xd0\x06\xa6\x98\x01\x81\x83\x82\x98N8\x06\x00\x04\xa9\x88N\x98\xf8V\xf1\x0e\x18\x04\xa1\x80N\x99\xfcp\x8c[1\xb0\xb71\xb2\xb6A^8,\x93\x99\x96\xf2\x80W\x11V\x00\x0c\x92\xf8o\x01&\xbaN\x10\x11\\\x08\x11]\xd1V\x00\t\x15\x9d\x8d\x82\x9d\xc68-\x84\xe8\xea\xf8n\xa1\x86\x86\x98>\xa1\x80\x0f\xd8\x07\x01N\x00\x0c\x08\x01\xf7f\x08@\xeek(\x01I\x82\x81H\xc2\xfb\xcb\x87\x08\x93C\xe9\x03\xe8\x03\xe9\x03\xe8\x00\xc1NJ\x84\x86\x85B\x1e\x84Z\x81JA\xc2\x00C#,\x15@\x0f<X\x07\xe8\x0b-\xab%\xc7\xec\x00\x97\x08\x00\x97]'\x08\n\xc28]A\x15\xc2\x00C#,\x15@\x0f<X\x07\xe8\x0b-\xab%\xc7\xec\x00@\x8eH\xd0\xd3\x89i\xc2\x00C#,\x15@\x0f<X\x07\xe8\x0b-\xab%\xc7\xec\x01\xc0\x82\x08A\x7f0\xf4R\n\x01\xe8\xf2\xd1\x94\xb3\x8eB1399SR\xc7\x05\x92_\t\xe0QQ\xc7\x05\xf2\xe1\xf4\x82\x10\x05\x13\x8d\x91\x16\xba\xf2\xe1\xf5\x03\xfa@0FP\x104Yp\x07\xc8\xcb\x00\x16\xcb\x1fP\x04\xcf\x16X\xcf\x16\x01\xcf\x16\x01\xfa\x02\xcc\xcb\x00\xc9\xedT\xe007(\xc0\x03\xe3\x02(\xc0\x00\x9c67\x108Ge\x14C0p\xf0\x05\xe0\x08\xc0\x02\x98UD\x10$\x10#\xf0\x05\xe0_\n\x84\x0f\xf2\xf0\t\x00\xd489\x82\x10;\x9a\xca\x00\x18\xbe\xf2\xe1\xc9SF\xc7\x05QR\xc7\x05\x15\xb1\xf2\xe1\xcap \x82\x10_\xcc=\x14!\x80\x10\xc8\xcb\x05(\xcf\x16!\xfa\x02\xcbj\xcb\x1f\x15\xcb?'\xcf\x16'\xcf\x16\x14\xca\x00#\xfa\x02\x13\xca\x00\xc9\x83\x06\xfb\x00qPfE\x15\x04p\x07\xc8\xcb\x00\x16\xcb\x1fP\x04\xcf\x16X\xcf\x16\x01\xcf\x16\x01\xfa\x02\xcc\xcb\x00\xc9\xedT\x00\x96\xc8\xcb\x1f\x13\xcb?#\xcf\x16P\x03\xcf\x16\xca\x00\x82\t\xc9\xc3\x80\xfa\x02\xca\x00\xc9q\x80\x18\xc8\xcb\x05&\xcf\x16p\xfa\x02\xcbj\xcc\xc9\x83\x06\xfb\x00qUPp\x07\xc8\xcb\x00\x16\xcb\x1fP\x04\xcf\x16X\xcf\x16\x01\xcf\x16\x01\xfa\x02\xcc\xcb\x00\xc9\xedT\xd6^e\x89")


class NftItemSale(Contract):

    @classmethod
    async def from_data(cls, provider: LiteClient, marketplace_address: Address, nft_address: Address, nft_owner_address: Address, full_price: int, fees: NftItemSaleFees, wc: int = 0, **kwargs) -> "NftItemSale":
        data = cls.create_data_cell(is_complete=False, created_at=int(time.time()), marketplace_address=marketplace_address, nft_address=nft_address, nft_owner_address=nft_owner_address, full_price=full_price, fees=fees, can_deploy_by_external=True)
        return await super().from_code_and_data(provider, wc, NFT_SALE_CODE, data, **kwargs)

    @staticmethod
    def create_data_cell(is_complete: bool, created_at: int, marketplace_address: Address, nft_address: Address, nft_owner_address: Address, full_price: int, fees: NftItemSaleFees, can_deploy_by_external: bool) -> Cell:
        return NftItemSaleData(is_complete, created_at, marketplace_address, nft_address, nft_owner_address, full_price, fees, can_deploy_by_external).serialize()

    @staticmethod
    def create_fees_cell(marketplace_fee_address: Address, marketplace_fee: int, royalty_address: Address, royalty_amount: int) -> Cell:
        return NftItemSaleFees(marketplace_fee_address, marketplace_fee, royalty_address, royalty_amount).serialize()

    @property
    def is_complete(self) -> bool:
        """
        :return: is_complete taken from contract data
        """
        return NftItemSaleData.deserialize(self.state.data.begin_parse()).is_complete

    @property
    def created_at(self) -> int:
        """
        :return: created_at taken from contract data
        """
        return NftItemSaleData.deserialize(self.state.data.begin_parse()).created_at

    @property
    def marketplace_address(self) -> Address:
        """
        :return: marketplace_address taken from contract data
        """
        return NftItemSaleData.deserialize(self.state.data.begin_parse()).marketplace_address

    @property
    def nft_address(self) -> Address:
        """
        :return: nft_address taken from contract data
        """
        return NftItemSaleData.deserialize(self.state.data.begin_parse()).nft_address

    @property
    def nft_owner_address(self) -> Address:
        """
        :return: nft_owner_address taken from contract data
        """
        return NftItemSaleData.deserialize(self.state.data.begin_parse()).nft_owner_address

    @property
    def full_price(self) -> int:
        """
        :return: full_price taken from contract data
        """
        return NftItemSaleData.deserialize(self.state.data.begin_parse()).full_price

    @property
    def fees_cell(self) -> NftItemSaleFees:
        """
        :return: fees_cell taken from contract data
        """
        return NftItemSaleData.deserialize(self.state.data.begin_parse()).fees_cell

    @property
    def can_deploy_by_external(self) -> bool:
        """
        :return: can_deploy_by_external taken from contract data
        """
        return NftItemSaleData.deserialize(self.state.data.begin_parse()).can_deploy_by_external

    async def get_sale_data(self) -> bool:
        return await super().run_get_method(method='get_sale_data', stack=[])
