import asyncio
from pytoniq import LiteBalancer
from pytoniq_core import begin_cell, Address
from pytoniq.contract.wallets.wallet import WalletV4R2


async def main():
    async with LiteBalancer.from_testnet_config(trust_level=2) as client:
        mnemo = []
        wallet = await WalletV4R2.from_mnemonic(client, mnemo)

        # deploy wallet if needed
        await wallet.deploy_via_external()

        await wallet.transfer(
            destination='EQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAM9c',
            body='comment',
            amount=1 * 10**8 # 0.1 TON
        )

        # or create message separately and then sign and send it
        message = wallet.create_wallet_internal_message(
            destination=Address('EQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAM9c'),
            send_mode=3,
            body=begin_cell().store_uint(0, 32).store_snake_string('comment').end_cell(),
            value=1 * 10**8  # 0.1 TON
        )

        await wallet.raw_transfer(msgs=[message])


if __name__ == '__main__':
    asyncio.run(main())
