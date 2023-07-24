import asyncio

from pytoniq.liteclient import LiteClient
from pytoniq.tlb import Block, ValueFlow, ShardAccounts
from pytoniq.tl import BlockIdExt


async def parse_block(client: LiteClient, block: BlockIdExt):
    full_block = await client.raw_get_block(block)
    value_flow: ValueFlow = full_block.value_flow
    print(value_flow.fees_collected.grams)  # 1007000010
    accounts: ShardAccounts = full_block.state_update.old.shard_state_unsplit.accounts
    print(accounts)  # ({40756874397635192262439020188088563828720515972064165042579090230945048213995: {'account': {'addr': Address<EQBaG5LL_CsF2hOq0D-nk71YcihyR71_1o33FnlG5cS56590>, 'storage_stat': {'used': {'cells': 22, 'bits': 5697, 'public_cells': None}, 'last_paid': 1690187357, 'due_payment': None}, 'storage': {'last_trans_lt': 39542571000003, 'balance': {'grams': 62352028502, 'other': None}, 'state': {'type_': 'account_active', 'state_init': {'split_depth': None, 'special': None, 'code': <Cell 288[0101FEB5FF6820E2FF0D9483E7E0D62C817D846789FB4AE580C878866D959DABD5C00007] -> 0 refs>, 'data': <Cell 321[000023E429A9A317B28A8042597CD3F1591A8B3A0EE7DAEF53E8FA7D5378A618AA80BE1EB48FC8E700] -> 0 refs>, 'library': None}}}}, 'last_trans_hash': b'\xfe}o\x83\xaf\x7f\xcf\x9e .\xc6\x0b\x96\x9el\xae8\xa6\xa9N[O\x89\xb8\xd3\xbaf\x89\xdf.\xdb\xd4', 'last_trans_lt': 39542571000001, 'cell': <Cell 320[FE7D6F83AF7FCF9E202EC60B969E6CAE38A6A94E5B4F89B8D3BA6689DF2EDBD4000023F6B8E5E0C1] -> 1 refs>}}, [{'split_depth': 0, 'balance': {'grams': 5553445990447918, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 5553446978130918, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 5553447242093167, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 5553449597627584, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 5553449680120571, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 5553502425603666, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 5553551498198270, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 5554171371732038, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 5554810996626740, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 5556695368115041, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 5570820341996106, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 5582868370124598, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 5668324449113770, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 5983054304100620, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 6643915352221766, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 99915737789528586, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 198985701626791490, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 379795173339356597, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 62352028502, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 62353858158, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 62451366404, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 64501434435, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 115078782628, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 132264475468, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 413217320912, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 431027638506, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 465652010665, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 855472014247, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 12697170876788, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 23277573167204, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 65993263389943, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 1628994778449415, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 2334912485572297, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 4383884219022332, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 5493159230272353, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 31059031289819148, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 126234268026871666, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 506029441366228263, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 719987176953810690, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 1802443900690706273, 'other': None}}, {'split_depth': 0, 'balance': {'grams': 2725693542936016491, 'other': None}}])


async def main():
    client = LiteClient.from_mainnet_config(ls_i=0, trust_level=2)

    await client.connect()

    old_blk = client.last_shard_blocks[0]  # last basechain block
    await parse_block(client, old_blk)
    while True:
        while client.last_shard_blocks[0] == old_blk:
            await asyncio.sleep(0)
            continue
        old_blk = client.last_shard_blocks[0]
        await parse_block(client, old_blk)


if __name__ == '__main__':
    asyncio.run(main())
