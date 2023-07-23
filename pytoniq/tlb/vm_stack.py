import copy

from .tlb import TlbScheme, TlbError
from ..boc.slice import Slice
from ..boc.builder import Builder
from ..boc.cell import Cell


class VmError(TlbError):
    pass


class VmStack(TlbScheme):
    """
    vm_stack#_ depth:(## 24) stack:(VmStackList depth) = VmStack;
    """
    @classmethod
    def serialize(cls, data: list) -> "Cell":
        result = Builder()
        result.store_uint(len(data), 24)  # depth
        return result.store_cell(VmStackList.serialize(data.copy())).end_cell()

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        depth = cell_slice.load_uint(24)
        return VmStackList.deserialize(cell_slice, depth)


class VmStackList(TlbScheme):
    """
    vm_stk_cons#_ {n:#} rest:^(VmStackList n) tos:VmStackValue = VmStackList (n + 1);
    vm_stk_nil#_ = VmStackList 0;
    """
    @classmethod
    def serialize(cls, data: list) -> Cell:
        builder = Builder()
        if len(data) == 0:
            return builder.end_cell()
        value = data.pop()
        builder.store_ref(cls.serialize(data))
        return builder.store_cell(VmStackValue.serialize(value)).end_cell()

    @classmethod
    def deserialize(cls, cell_slice: Slice, n_p_1: int):  # n_p_1 stands for n plus 1 or n + 1
        if n_p_1 == 0:
            return []
        result = cls.deserialize(cell_slice.load_ref().begin_parse(), n_p_1 - 1)
        return result + [VmStackValue.deserialize(cell_slice)]


class VmStackValue(TlbScheme):
    """
    vm_stk_null#00 = VmStackValue;
    vm_stk_tinyint#01 value:int64 = VmStackValue;
    vm_stk_int#0201_ value:int257 = VmStackValue;
    vm_stk_nan#02ff = VmStackValue;
    vm_stk_cell#03 cell:^Cell = VmStackValue;
    vm_stk_slice#04 _:VmCellSlice = VmStackValue;
    vm_stk_builder#05 cell:^Cell = VmStackValue;
    vm_stk_cont#06 cont:VmCont = VmStackValue;
    vm_stk_tuple#07 len:(## 16) data:(VmTuple len) = VmStackValue;
    """

    @classmethod
    def serialize(cls, value) -> Cell:
        builder = Builder()
        if value is None:
            builder.store_bytes(b'\x00')
        elif isinstance(value, int):
            if value.bit_length() <= 64:
                builder.store_bytes(b'\x01')
                builder.store_int(value, 64)
            else:
                builder.store_bits('000000100000000')  # 0201_
                # builder.store_bytes(b'\x02\x01')
                builder.store_int(value, 257)
        elif isinstance(value, bytes):
            builder.store_bits('0000001000000000')  # 0200
            assert len(value) <= 32, 'bytes length should be less than 32'
            builder.store_bytes(value)
        elif isinstance(value, Cell):
            builder.store_bytes(b'\x03')
            builder.store_ref(value)
        elif isinstance(value, Slice):
            builder.store_bytes(b'\x04')
            builder.store_cell(VmCellSlice.serialize(value))
        elif isinstance(value, Builder):
            builder.store_bytes(b'\x05')
            builder.store_ref(value.end_cell())
        elif isinstance(value, VmCont):
            builder.store_bytes(b'\x06')
            builder.store_cell(VmCont.serialize(value))
        elif isinstance(value, VmTuple):
            builder.store_bytes(b'\x07')
            builder.store_uint(len(value), 16)
            builder.store_cell(VmTuple.serialize(value))
        return builder.end_cell()

    @classmethod
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.preload_bits(15).to01()
        if tag == '000000100000000':  # #0201_
            cell_slice.load_bits(15)
            return cell_slice.load_int(257)
            # actually the code below is more convenient (for keys for e.g.) but may work incorrectly for a big positive integer
            if cell_slice.preload_bit():
                return cell_slice.load_int(257)
            cell_slice.load_bit()
            return cell_slice.load_bytes(32)

        tag = cell_slice.preload_bytes(2)
        if tag[:1] == b'\x00':
            cell_slice.load_bytes(1)
            return None
        elif tag[:1] == b'\x01':
            cell_slice.load_bytes(1)
            return cell_slice.load_int(64)
        elif tag == b'\x02\xff':
            cell_slice.load_bytes(2)
            return None
        elif tag[:1] == b'\x03':
            cell_slice.load_bytes(1)
            return cell_slice.load_ref()
        elif tag[:1] == b'\x05':
            cell_slice.load_bytes(1)
            return cell_slice.load_ref().to_builder()
        elif tag[:1] == b'\x04':
            cell_slice.load_bytes(1)
            return VmCellSlice.deserialize(cell_slice)
        elif tag[:1] == b'\x06':
            cell_slice.load_bytes(1)
            return VmCont.deserialize(cell_slice)
        elif tag[:1] == b'\x07':
            cell_slice.load_bytes(1)
            tuple_len = cell_slice.load_uint(16)
            return VmTuple.deserialize(cell_slice, tuple_len)


class VmTuple(TlbScheme):
    """
    vm_tuple_nil$_ = VmTuple 0;
    vm_tuple_tcons$_ {n:#} head:(VmTupleRef n) tail:^VmStackValue = VmTuple (n + 1);
    """
    """
    Usage:
        tuple = VmTuple([1, 2, <Slice 32[00000203] -> 2 refs>])
        VmTuple.serialize(tuple) -> Cell
        tuple = VmTuple.deserialize(cell_slice: Slice, length: int) -> <VmTuple [1, 2, <Slice 32[00000203] -> 2 refs>]>
        tuple.list -> [1, 2, <Slice 32[00000203] -> 2 refs>]
    """

    def __init__(self, list_: list):
        self.list: list = list_

    def __add__(self, other: "VmTuple"):
        self.list += other.list

    def __call__(self, index: int):
        return self.list[index]

    def __getitem__(self, index: int):
        return self.__call__(index)

    def __len__(self):
        return len(self.list)

    def __repr__(self):
        return f'<VmTuple {self.list} >'

    def append(self, item):
        self.list.append(item)
        return self

    def pop(self, index: int = -1):
        return self.list.pop(index)

    @classmethod
    def serialize(cls, values: "VmTuple") -> Cell:
        if len(values) == 0:
            return Cell.empty()
        builder = Builder()
        value = values.pop()
        builder.store_cell(VmTupleRef.serialize(values))
        builder.store_ref(VmStackValue.serialize(value))
        return builder.end_cell()

    @classmethod
    def deserialize(cls, cell_slice: Slice, length: int) -> "VmTuple":
        if length == 0:
            return VmTuple([])

        return VmTupleRef.deserialize(cell_slice, length - 1).append(VmStackValue.deserialize(cell_slice.load_ref().begin_parse()))


class VmTupleRef(TlbScheme):
    """
    vm_tupref_nil$_ = VmTupleRef 0;
    vm_tupref_single$_ entry:^VmStackValue = VmTupleRef 1;
    vm_tupref_any$_ {n:#} ref:^(VmTuple (n + 2)) = VmTupleRef (n + 2);
    """

    @classmethod
    def serialize(cls, values: VmTuple) -> Cell:
        if len(values) == 0:
            return Cell.empty()
        if len(values) == 1:
            return Builder().store_ref(VmStackValue.serialize(values[0])).end_cell()
        return Builder().store_ref(VmTuple.serialize(values)).end_cell()

    @classmethod
    def deserialize(cls, cell_slice: Slice, length: int) -> VmTuple:
        if length == 0:
            return VmTuple([])
        if length == 1:
            return VmTuple([VmStackValue.deserialize(cell_slice.load_ref().begin_parse())])
        return VmTuple.deserialize(cell_slice.load_ref().begin_parse(), length)


class VmCellSlice(TlbScheme):
    """
    _ cell:^Cell st_bits:(## 10) end_bits:(## 10) { st_bits <= end_bits }
    st_ref:(#<= 4) end_ref:(#<= 4) { st_ref <= end_ref } = VmCellSlice;
    """

    @classmethod
    def serialize(cls, value: Slice) -> Cell:
        builder = Builder()
        builder.store_ref(Builder().store_slice(value).end_cell())
        builder.store_uint(0, 10)  # st_bits
        builder.store_uint(len(value.bits), 10)  # end_bits
        builder.store_uint(0, 3)  # st_ref
        builder.store_uint(len(value.refs) - value.ref_offset, 3)  # end_ref
        return builder.end_cell()

    @classmethod
    def deserialize(cls, cell_slice: Slice) -> Slice:
        cell = cell_slice.load_ref()
        st_bits = cell_slice.load_uint(10)
        end_bits = cell_slice.load_uint(10)
        if not st_bits <= end_bits:
            raise VmError(f'{cls.__name__} deserialization error: st_bits {st_bits}, end_bits {end_bits}')

        st_ref = cell_slice.load_uint(3)
        end_ref = cell_slice.load_uint(3)

        if not st_ref <= end_ref:
            raise VmError(f'{cls.__name__} deserialization error: st_ref {st_ref}, end_ref {end_ref}')

        result = Slice.from_cell(cell)
        result.refs = result.refs[st_ref: end_ref]
        result.bits = result.bits[st_bits: end_bits]

        return result


class VmCont(TlbScheme):
    """
    vmc_std$00 cdata:VmControlData code:VmCellSlice = VmCont;
    vmc_envelope$01 cdata:VmControlData next:^VmCont = VmCont;
    vmc_quit$1000 exit_code:int32 = VmCont;
    vmc_quit_exc$1001 = VmCont;
    vmc_repeat$10100 count:uint63 body:^VmCont after:^VmCont = VmCont;
    vmc_until$110000 body:^VmCont after:^VmCont = VmCont;
    vmc_again$110001 body:^VmCont = VmCont;
    vmc_while_cond$110010 cond:^VmCont body:^VmCont after:^VmCont = VmCont;
    vmc_while_body$110011 cond:^VmCont body:^VmCont after:^VmCont = VmCont;
    vmc_pushint$1111 value:int32 next:^VmCont = VmCont;
    """

    def __init__(self, type_, **kwargs):
        self.type_ = type_
        for k, v in kwargs.items():
            setattr(self, k, v)

    @classmethod
    def serialize(cls, value: "VmCont") -> "Cell":
        builder = Builder()

        if value.type_ == 'vmc_std':
            builder.store_bits('00')
            builder.store_cell(VmControlData.serialize(value.cdata))  # cdata:VmControlData
            builder.store_cell(VmCellSlice.serialize(value.code))  # code:VmCellSlice
        elif value.type_ == 'vmc_envelope':
            builder.store_bits('01')
            builder.store_cell(VmControlData.serialize(value.cdata))  # cdata:VmControlData
            builder.store_ref(cls.serialize(value.next))  # next:^VmCont
        elif value.type_ == 'vmc_quit':
            builder.store_bits('1000')
            builder.store_int(value.exit_code, 32)  # exit_code:int32
        elif value.type_ == 'vmc_quit_exc':
            builder.store_bits('1001')
        elif value.type_ == 'vmc_repeat':
            builder.store_bits('10100')
            builder.store_uint(value.count, 63)  # count:uint63
            builder.store_ref(cls.serialize(value.body))  # body:^VmCont
            builder.store_ref(cls.serialize(value.after))  # after:^VmCont
        elif value.type_ == 'vmc_until':
            builder.store_bits('110000')
            builder.store_ref(cls.serialize(value.body))  # body:^VmCont
            builder.store_ref(cls.serialize(value.after))  # after:^VmCont
        elif value.type_ == 'vmc_again':
            builder.store_bits('110001')
            builder.store_ref(cls.serialize(value.body))  # body:^VmCont
        elif value.type_ == 'vmc_while_cond':
            builder.store_bits('110010')
            builder.store_ref(cls.serialize(value.cond))  # cond:^VmCont
            builder.store_ref(cls.serialize(value.body))  # body:^VmCont
            builder.store_ref(cls.serialize(value.after))  # after:^VmCont
        elif value.type_ == 'vmc_while_body':
            builder.store_bits('110011')
            builder.store_ref(cls.serialize(value.cond))  # cond:^VmCont
            builder.store_ref(cls.serialize(value.body))  # body:^VmCont
            builder.store_ref(cls.serialize(value.after))  # after:^VmCont
        elif value.type_ == 'vmc_pushint':
            builder.store_bits('1111')
            builder.store_int(value.value, 32)  # value:int32
            builder.store_ref(cls.serialize(value.next))  # next:^VmCont
        return builder.end_cell()

    @classmethod
    def deserialize(cls, cell_slice: Slice) -> "VmCont":
        tag = cell_slice.preload_bits(6).to01()
        if tag[:2] == '00':
            return cls('vmc_std', cdata=VmControlData.deserialize(cell_slice), code=VmCellSlice.deserialize(cell_slice))
        elif tag[:2] == '01':
            return cls('vmc_envelope', cdata=VmControlData.deserialize(cell_slice), next=cls.deserialize(cell_slice.load_ref().begin_parse()))
        elif tag[:4] == '1000':
            return cls('vmc_quit', exit_code=cell_slice.load_int(32))
        elif tag[:4] == '1001':
            return cls('vmc_quit_exc')
        elif tag[:5] == '10100':
            return cls('vmc_repeat', count=cell_slice.load_uint(63), body=cls.deserialize(cell_slice.load_ref().begin_parse()), after=cls.deserialize(cell_slice.load_ref().begin_parse()))
        elif tag[:6] == '110000':
            return cls('vmc_until', body=cls.deserialize(cell_slice.load_ref().begin_parse()), after=cls.deserialize(cell_slice.load_ref().begin_parse()))
        elif tag[:6] == '110001':
            return cls('vmc_again', body=cls.deserialize(cell_slice.load_ref().begin_parse()))
        elif tag[:6] == '110010':
            return cls('vmc_while_cond', cond=cls.deserialize(cell_slice.load_ref().begin_parse()), body=cls.deserialize(cell_slice.load_ref().begin_parse()), after=cls.deserialize(cell_slice.load_ref().begin_parse()))
        elif tag[:6] == '110011':
            return cls('vmc_while_body', cond=cls.deserialize(cell_slice.load_ref().begin_parse()), body=cls.deserialize(cell_slice.load_ref().begin_parse()), after=cls.deserialize(cell_slice.load_ref().begin_parse()))
        elif tag[:4] == '1111':
            return cls('vmc_pushint', value=cell_slice.load_int(32), next=cls.deserialize(cell_slice.load_ref().begin_parse()))


class VmControlData(TlbScheme):
    """
    vm_ctl_data$_ nargs:(Maybe uint13) stack:(Maybe VmStack) save:VmSaveList
    cp:(Maybe int16) = VmControlData;
    """
    def __init__(self, type_, **kwargs):
        self.type_ = type_
        for k, v in kwargs.items():
            setattr(self, k, v)

    @classmethod
    def serialize(cls, value: "VmControlData") -> Cell:
        builder = Builder()

        if value.nargs:
            builder.store_bit_int(1)
            builder.store_uint(value.nargs, 13)
        else:
            builder.store_bit_int(0)

        if value.stack:
            builder.store_bit_int(1)
            builder.store_cell(value.stack)
        else:
            builder.store_bit_int(0)

        builder.store_cell(VmSaveList.serialize(value.save))

        if value.cp:
            builder.store_bit_int(1)
            builder.store_int(value.cp, 16)
        else:
            builder.store_bit_int(0)

        return builder.end_cell()

    @classmethod
    def deserialize(cls, cell_slice: Slice) -> "VmControlData":
        kwargs = {}
        is_nargs = cell_slice.load_bit()
        if is_nargs:
            kwargs['nargs'] = cell_slice.load_uint(13)
        is_stack = cell_slice.load_bit()
        if is_stack:
            kwargs['stack'] = VmStack.deserialize(cell_slice)
        kwargs['save'] = VmSaveList.deserialize(cell_slice)
        is_cp = cell_slice.load_bit()
        if is_cp:
            kwargs['cp'] = cell_slice.load_int(16)
        return cls('vm_ctl_data', **kwargs)


class VmSaveList(TlbScheme):
    """
    _ cregs:(HashmapE 4 VmStackValue) = VmSaveList;
    """
    @classmethod
    def serialize(cls, value: "HashMap") -> Cell:
        return Builder().store_dict(value).end_cell()

    @classmethod
    def deserialize(cls, cell_slice: Slice) -> "HashMap":
        return cell_slice.load_dict(4)
