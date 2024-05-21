from pytoniq_core.tl.block import BlockIdExt

init_mainnet_blocks = [
    BlockIdExt.from_dict({
        "root_hash": "61192b72664cbcb06f8da9f0282c8bdf0e2871e18fb457e0c7cca6d502822bfe",
        "seqno": 27747086,
        "file_hash": "378db1ccf9c98c3944de1c4f5ce6fea4dcd7a26811b695f9019ccc3e7200e35b",
        "workchain": -1,
        "shard": -9223372036854775808
    }),
    BlockIdExt.from_dict({
        "root_hash": "5695b27cd38b9bc46ab7a09967d7591aa2513b7372ae51c760dd64d682db27a8",
        "seqno": 34835953,
        "file_hash": "f28d76297e7806d24cf111110f527ded07b565693ad4b208c97c9d9419e2c4af",
        "workchain": -1,
        "shard": -9223372036854775808
    }),
]

init_testnet_blocks = [
    BlockIdExt.from_dict({
        "file_hash": "c516b1814c204d76056f5e989d1f90f9556c7332e5ea3998c2fce143f9dcae1e",
        "seqno": 5176527,
        "root_hash": "4a83cba8c7bd0f3dba6093ce1833870294d27b98b491716d466461ff33cc1ae2",
        "workchain": -1,
        "shard": -9223372036854775808
    })
]
