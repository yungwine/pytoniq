import asyncio
from pytoniq import LiteBalancer, WalletV3R2, Address, Cell, WalletMessage, begin_cell
from pytoniq_core.tlb.block import CurrencyCollection, ExtraCurrencyCollection


async def send_ec():
    async with LiteBalancer.from_testnet_config(trust_level=2) as client:
        mnemo = []
        wallet = await WalletV3R2.from_mnemonic(client, mnemo)

        addr = Address('EQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAM9c')
        currency_id = 100
        amount = 1*10**8
        body = begin_cell().store_uint(0, 32).store_snake_string('123456').end_cell()  # comment 123456

        value = CurrencyCollection(grams=0, other=ExtraCurrencyCollection({currency_id: amount}))
        message = WalletV3R2.create_internal_msg(dest=addr, value=value, body=body)
        msg = WalletMessage(send_mode=3, message=message)
        await wallet.raw_transfer(msgs=[msg])


async def receive_ec(addr: str):
    async with LiteBalancer.from_testnet_config(trust_level=2) as client:
        ec_id = 100
        last_lt = 0
        while True:
            trs = await client.get_transactions(address=addr, count=16)
            if last_lt == 0:
                last_lt = trs[0].lt
            for tr in trs:
                if tr.lt <= last_lt:
                    continue
                last_lt = tr.lt
                if not tr.in_msg.is_internal:
                    continue
                ec_dict = tr.in_msg.info.value.other.dict
                if ec_dict is not None and ec_dict.get(ec_id, 0) != 0:
                    cs = tr.in_msg.body.begin_parse()
                    if cs.remaining_bits >= 32 and cs.load_uint(32) == 0:
                        comment = cs.load_snake_string()
                    else:
                        print('no comment in tr')
                        continue
                    if tr.description.bounce and tr.description.bounce.type_ == 'ok':
                        print('bounced tr')
                        continue
                    print(f'Received {ec_dict[ec_id]} EC from {tr.in_msg.info.src} with comment: {comment}')
                    return {'amount': ec_dict[ec_id], 'from': tr.in_msg.info.src}
            await asyncio.sleep(1)


if __name__ == '__main__':
    asyncio.run(send_ec())
    asyncio.run(receive_ec('addr'))
