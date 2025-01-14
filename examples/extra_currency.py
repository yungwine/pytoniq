import asyncio
from pytoniq import LiteBalancer, WalletV3R2, Address, Cell, WalletMessage
from pytoniq_core.tlb.block import CurrencyCollection, ExtraCurrencyCollection


async def main():
    async with LiteBalancer.from_testnet_config(trust_level=2) as client:
        mnemo = []
        wallet = await WalletV3R2.from_mnemonic(client, mnemo)

        addr = Address('EQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAM9c')
        currency_id = 100
        amount = 1*10**8

        value = CurrencyCollection(grams=0, other=ExtraCurrencyCollection({currency_id: amount}))
        message = WalletV3R2.create_internal_msg(dest=addr, value=value, body=Cell.empty())
        msg = WalletMessage(send_mode=3, message=message)
        await wallet.raw_transfer(msgs=[msg])


if __name__ == '__main__':
    asyncio.run(main())
