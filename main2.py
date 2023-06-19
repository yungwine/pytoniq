from tonpylib.boc.dict.dict import HashMap
from tonpylib.boc.address import Address
from tonpylib.boc.builder import Builder


dict = HashMap(256, value_serializer=lambda src, dest: dest.store_string(src))

cell = dict.set('name', 'tonpy', hash_key=True).set('description', 'the best lib', hash_key=True).serialize()

res = HashMap.from_cell(cell, 256)
# print(res.map)

new_dict = HashMap(267).with_coins_values()
new_dict.set(key=Address('EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG'), value=15)\
    .set(key=Address('EQCD39VS5jcptHL8vMjEXrzGaRcCVYto7HUn4bpAOg8xqB2N'), value=10)

new_dict_cell = new_dict.serialize()
print(new_dict_cell)

# 22[817000] -> {
# 	297[BFF7ADE33CC37032184B0ECEF80219C935266C972CBEEEC553021B22D6105E8BC10000000780],
# 	297[BFC1EFEAA9731B94DA397E5E64622F5E63348B812AC5B4763A93F0DD201D0798D40000000780]
# }


def key_deserializer(src):
    return Builder().store_bits(src).to_slice().load_address()


def value_deserializer(src):
    return src.load_coins()


print(HashMap.parse(new_dict_cell, 267, key_deserializer, value_deserializer))

# {
#     Address<EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG>: 15,
#     Address<EQCD39VS5jcptHL8vMjEXrzGaRcCVYto7HUn4bpAOg8xqB2N>: 10
# }
