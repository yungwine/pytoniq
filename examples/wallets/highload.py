import asyncio
from pytoniq import LiteBalancer
from pytoniq_core import Cell
from pytoniq.contract.wallets.highload_v3 import HighloadWalletV3


async def main():
    async with LiteBalancer.from_mainnet_config(trust_level=2) as client:
        mnemo = []
        wallet = await HighloadWalletV3.from_mnemonic(client, mnemo)

        # deploy wallet if needed
        await wallet.deploy_via_external()

        # send 1000 messages to zero address, each message has 3 ton attached and empty body
        await wallet.transfer(destinations=['EQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAM9c'] * 1000, amounts=[3 * 10**9] * 1000, bodies=[Cell.empty()] * 1000)


if __name__ == '__main__':
    asyncio.run(main())
