import random
import timeit

from tonpylib.boc.builder import Builder
from tonpylib.boc.cell import Cell
from tonpylib.boc.slice import Slice
from tonsdk.boc import Cell as TonsdkCell, begin_cell


builder = Builder()
cell = builder \
        .store_uint(15, 32) \
        .store_ref(
            Builder()
            .store_bit(1)
            .store_ref(
                Builder().end_cell()
            ).end_cell()
        ) \
        .store_ref(
            Builder()
            .store_bit(0)
            .store_ref(
                Builder().end_cell()
            )
            .end_cell()
        ) \
    .end_cell()


def create_cell():
    builder = Builder()
    for j in range(3):
        ref = Builder()
        for i in range(3):
            ref.store_ref(
                Builder().store_uint(random.randint(100, 1000), 32).end_cell()
            )
        builder.store_ref(ref.end_cell())

    result = builder.end_cell()
    return result


def create_tonsdk_cell():
    builder = begin_cell()
    for j in range(3):
        ref = begin_cell()
        for i in range(3):
            ref.store_ref(
                begin_cell().store_uint(random.randint(100, 1000), 32).end_cell()
            )
        builder.store_ref(ref.end_cell())

    result = builder.end_cell()
    return result


# print(timeit.timeit('cell = create_cell()\nCell.one_from_boc(cell.to_boc())', globals=globals(), number=1000))
# print(timeit.timeit('''Slice.one_from_boc(b'\\xb5\\xee\\x9cr\\x81\\x01\\x04\\x01\\x00\\x12\\x00\\x08\\x04\\x04\\x02\\x02\\x08\\x00\\x00\\x00\\x0f\\x01\\x02\\x01\\x01\\xc0\\x03\\x01\\x01@\\x03\\x00\\x00')''', globals=globals(), number=10000))


# boc = 'b5ee9c72810104010012000804040202080000000f01020101c003010140030000'
# cell = Cell.one_from_boc(boc)

print(cell)
builder = cell.to_builder()
builder.store_address('EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG')
cell = builder.end_cell()
print(1)
print(cell.to_boc())
print(Slice.one_from_boc(cell.to_boc()))

cell = Cell.one_from_boc(b'\xb5\xee\x9cr\x01\x01\x04\x01\x004\x00\x02K\x00\x00\x00\x0f\x80\r\xebx\xcf0\xdc\x0c\x86\x12\xc3\xb3\xbe\x00\x86rMI\x9b%\xcb/\xbb\xb1T\xc0\x86\xc8\xb5\x84\x17\xa2\xf0P\x01\x02\x01\x01\xc0\x03\x01\x01@\x03\x00\x00')

# 304[0000000F800DEB78CF30DC0C8612C3B3BE0086724D499B25CB2FBBB154C086C8B58417A2F050] -> {
# 	8[C0] -> {
# 		0[]
# 	},
# 	8[40] -> {
# 		0[]
# 	}
# }

slice = cell.to_slice()
print(slice.load_uint(32))  # 15
print(slice.load_address())  # EQBvW8Z5huBkMJYdnfAEM5JqTNkuWX3diqYENkWsIL0XggGG

# print(.to_boc())
# print(cell)
# print(cell, cell.to_boc())
# tonsdk_cell = cell.to_tonsdk_cell(TonsdkCell)
# print(tonsdk_cell)
# print(timeit.timeit('cell = create_tonsdk_cell()\nCell.one_from_boc(cell.to_boc())', globals=globals(), number=1000))
