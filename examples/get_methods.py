import asyncio
import logging

from pytoniq import LiteClient, WalletV4R2, Address


async def main():
    logging.basicConfig(level=logging.INFO)

    client = LiteClient.from_mainnet_config(ls_i=0, trust_level=2)

    await client.connect()

    """wallet seqno"""
    result = await client.run_get_method(address='EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG', method='seqno', stack=[])
    print(result)  # [242]
    wallet = await WalletV4R2.from_address(provider=client, address='EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG')
    print(wallet.seqno)  # 242
    print(await wallet.get_seqno())  # 242
    print(await wallet.run_get_method(method='seqno', stack=[]))  # [242]

    """dex router get method"""
    result = await client.run_get_method(address='EQB3ncyBUTjZUA5EnFKR5_EnOMI9V1tTEAAPaiU71gc4TiUt', method='get_router_data', stack=[])
    print(result)  # [0, <Slice 267[80093377825F7267A94C4EF8966051F874BF125171483071FC33E1E05EBFF4DF6E00] -> 0 refs>, <Cell 130[0000000000000000000000000000000000] -> 1 refs>, <Cell 80[FF00F4A413F4BCF2C80B] -> 1 refs>, <Cell 80[FF00F4A413F4BCF2C80B] -> 1 refs>, <Cell 80[FF00F4A413F4BCF2C80B] -> 1 refs>]
    print(result[1].load_address())  # EQBJm7wS-5M9SmJ3xLMCj8Ol-JKLikGDj-GfDwL1_6b7cENC

    """jetton wallets"""
    owner_address = Address('EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG')
    request_stack = [owner_address.to_cell().begin_parse()]
    result = await client.run_get_method(address='EQBynBO23ywHy_CgarY9NK9FTz0yDsG82PtcbSTQgGoXwiuA', method='get_wallet_address', stack=request_stack)
    print(result)   # [<Slice 267[801B54D587424F634D8AC9DC74071390A2EBDA9F0410E4F19F734DD133C9F136F4A0] -> 0 refs>]
    jetton_wallet_address = result[0].load_address()
    print(jetton_wallet_address)  # EQDapqw6EnsabFZO46A4nIUXXtT4IIcnjPuabomeT4m3paST

    result = await client.run_get_method(address='EQDapqw6EnsabFZO46A4nIUXXtT4IIcnjPuabomeT4m3paST', method='get_wallet_data', stack=[])
    print(result)  # [2005472, <Slice 267[800DEB78CF30DC0C8612C3B3BE0086724D499B25CB2FBBB154C086C8B58417A2F040] -> 0 refs>, <Slice 267[800E538276DBE580F97E140D56C7A695E8A9E7A641D8379B1F6B8DA49A100D42F840] -> 0 refs>, <Cell 80[FF00F4A413F4BCF2C80B] -> 1 refs>]

    await client.close()

if __name__ == '__main__':
    asyncio.run(main())
