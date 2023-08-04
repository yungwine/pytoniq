from ..contract import Contract, ContractError
from ...liteclient.client import LiteClient
from pytoniq_core.boc import Cell, Builder, HashMap
from pytoniq_core.boc.address import Address
from pytoniq_core.tlb.custom.nft import NftItemData

NFT_CODE = Cell.one_from_boc(b'\xb5\xee\x9crA\x02\r\x01\x00\x01\xd0\x00\x01\x14\xff\x00\xf4\xa4\x13\xf4\xbc\xf2\xc8\x0b\x01\x02\x01b\x02\x03\x02\x02\xce\x04\x05\x00\t\xa1\x1f\x9f\xe0\x05\x02\x01 \x06\x07\x02\x01 \x0b\x0c\x02\xd7\x0c\x88q\xc0$\x97\xc0\xf844\xc0\xc0\\l$\x97\xc0\xf8>\x90>\x90\x0c~\x80\x0c\\u\xc8~\x80\x0c~\x80\x0c<\x00\x81,\xe3\x85\x0c\x1b\x08\x8d\x14\x8c\xb1\xc1|\xb8e@~\x905\x0c\x04\x08\xfc\x00\xf8\x01\xb4\xc7\xf4\xcf\xe0\x84\x17\xf3\x0fE\x14\x8c.\xa3\xa1\xcc\x84\r\xd7\x8c\x90\x04\xf8\x0c\r\r\rM`\x84\x0b\xf2\xc9\xa8\x84\xae\xb8\xc0\x97\xc1!\x03\xfc\xbc \x08\t\x00\x11>\x91\x0c\x1c.\xbc\xb8S`\x01\xf6Q5\xc7\x05\xf2\xe1\x91\xfa@!\xf0\x01\xfa@\xd2\x001\xfa\x00\x82\n\xfa\xf0\x80\x1b\xa1!\x94S\x15\xa0\xa1\xde"\xd7\x0b\x01\xc3\x00 \x92\x06\xa1\x916\xe2 \xc2\xff\xf2\xe1\x92!\x8e>\x82\x10\x05\x13\x8d\x91\xc8P\t\xcf\x16P\x0b\xcf\x16q$I\x14TF\xa0p\x80\x10\xc8\xcb\x05P\x07\xcf\x16P\x05\xfa\x02\x15\xcbj\x12\xcb\x1f\xcb?"n\xb3\x94X\xcf\x17\x01\x912\xe2\x01\xc9\x01\xfb\x00\x10G\x94\x10*7[\xe2\n\x00rp\x82\x10\x8bw\x175\x05\xc8\xcb\xffP\x04\xcf\x16\x10$\x80@p\x80\x10\xc8\xcb\x05P\x07\xcf\x16P\x05\xfa\x02\x15\xcbj\x12\xcb\x1f\xcb?"n\xb3\x94X\xcf\x17\x01\x912\xe2\x01\xc9\x01\xfb\x00\x00\x82\x02\x8e5&\xf0\x01\x82\x10\xd52v\xdb\x107D\x00mqp\x80\x10\xc8\xcb\x05P\x07\xcf\x16P\x05\xfa\x02\x15\xcbj\x12\xcb\x1f\xcb?"n\xb3\x94X\xcf\x17\x01\x912\xe2\x01\xc9\x01\xfb\x00\x93024\xe2U\x02\xf0\x03\x00;;Q44\xcf\xfe\x90\x085\xd2p\x80&\x9f\xc0~\x905\x0c\x04\t\x04\x08\xf8\x0c\x1c\x16[[`\x00\x1d\x00\xf22\xcf\xd63\xc5\x80s\xc5\xb32{U \xbfu\x04\x1b')


class NftItem(Contract):

    @classmethod
    async def from_data(cls, provider: LiteClient, index: int, collection_address: Address, owner_address: Address, content: Cell, wc: int = 0, **kwargs) -> "NftItem":
        data = cls.create_data_cell(index, collection_address, owner_address, content)
        return await super().from_code_and_data(provider, wc, NFT_CODE, data, **kwargs)

    @staticmethod
    def create_data_cell(index: int, collection_address: Address, owner_address: Address, content: Cell) -> Cell:
        return NftItemData(index=index, collection_address=collection_address, owner_address=owner_address, content=content).serialize()

    @property
    def index(self) -> int:
        """
        :return: index taken from contract data
        """
        return NftItemData.deserialize(self.state.data.begin_parse()).index

    @property
    def collection_address(self) -> Address:
        """
        :return: collection_address taken from contract data
        """
        return NftItemData.deserialize(self.state.data.begin_parse()).collection_address

    @property
    def owner_address(self) -> Address:
        """
        :return: owner_address taken from contract data
        """
        return NftItemData.deserialize(self.state.data.begin_parse()).owner_address

    @property
    def content(self) -> Cell:
        """
        :return: old_queries taken from contract data
        """
        return NftItemData.deserialize(self.state.data.begin_parse()).content

    async def get_nft_data(self) -> bool:
        return await super().run_get_method(method='get_nft_data', stack=[])
