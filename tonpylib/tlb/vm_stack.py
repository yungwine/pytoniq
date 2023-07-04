from .tlb import TlbScheme, TlbError
from ..boc.slice import Slice


class VmError(TlbError):
    pass


class VmStack(TlbScheme):
    """
    vm_stack#_ depth:(## 24) stack:(VmStackList depth) = VmStack;
    """
    @staticmethod
    def serialize():
        pass

    @staticmethod
    def deserialize(cell_slice: Slice):
        depth = cell_slice.load_uint(24)
        return VmStackList.deserialize(cell_slice, depth)


class VmStackList:
    """
    vm_stk_cons#_ {n:#} rest:^(VmStackList n) tos:VmStackValue = VmStackList (n + 1);
    vm_stk_nil#_ = VmStackList 0;
    """
    @staticmethod
    def serialize():
        pass

    @classmethod
    def deserialize(cls, cell_slice: Slice, n_p_1: int):  # n_p_1 stands for n plus 1 or n + 1
        if n_p_1 == 0:
            return []
        result = []
        result += cls.deserialize(cell_slice.load_ref(), n_p_1 - 1)
        return result + [VmStackValue.deserialize(cell_slice)]
        return result


class VmStackValue:
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
    def deserialize(cls, cell_slice: Slice):
        tag = cell_slice.preload_bytes(2)
        if tag[:1] == b'\x00':
            cell_slice.load_bytes(1)
            return None
        elif tag[:1] == b'\x01':
            cell_slice.load_bytes(1)
            return cell_slice.load_int(64)
        elif tag == b'\x02\x01':
            cell_slice.load_bytes(2)
            return cell_slice.load_int(257)
        elif tag == b'\x02\xff':
            cell_slice.load_bytes(2)
            return None
        elif tag[:1] in (b'\x03', b'\x05'):
            cell_slice.load_bytes(1)
            return cell_slice.load_ref()
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


class VmTuple:
    """
    vm_tuple_nil$_ = VmTuple 0;
    vm_tuple_tcons$_ {n:#} head:(VmTupleRef n) tail:^VmStackValue = VmTuple (n + 1);
    """
    """
    Usage:
        VmTuple([1, 2, <Slice 32[00000203] -> 2 refs>]).serialize() -> Slice
        VmTuple.deserialize(cell_slice, length) -> <VmTuple [1, 2, <Slice 32[00000203] -> 2 refs>]>;
            <VmTuple [1, 2, <Slice 32[00000203] -> 2 refs>]>.list -> [1, 2, <Slice 32[00000203] -> 2 refs>]
    """

    def __init__(self, list_: list):
        self.list = list_

    def __add__(self, other: "VmTuple"):
        self.list += other.list

    def __call__(self, index: int):
        return self.list[index]

    def __repr__(self):
        return f'<VmTuple {self.list} >'

    def append(self, item):
        self.list.append(item)
        return self

    @classmethod
    def deserialize(cls, cell_slice: Slice, length: int) -> "VmTuple":
        if length == 0:
            return VmTuple([])

        return VmTupleRef.deserialize(cell_slice, length - 1).append(VmStackValue.deserialize(cell_slice.load_ref()))


class VmTupleRef:
    """
    vm_tupref_nil$_ = VmTupleRef 0;
    vm_tupref_single$_ entry:^VmStackValue = VmTupleRef 1;
    vm_tupref_any$_ {n:#} ref:^(VmTuple (n + 2)) = VmTupleRef (n + 2);
    """

    @classmethod
    def deserialize(cls, cell_slice: Slice, length: int) -> VmTuple:
        if length == 0:
            return VmTuple([])
        if length == 1:
            return VmTuple([VmStackValue.deserialize(cell_slice.load_ref())])
        return VmTuple.deserialize(cell_slice.load_ref(), length)


class VmCellSlice:
    """
    _ cell:^Cell st_bits:(## 10) end_bits:(## 10) { st_bits <= end_bits }
    st_ref:(#<= 4) end_ref:(#<= 4) { st_ref <= end_ref } = VmCellSlice;
    """

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


class VmCont:
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
    def deserialize(cls, cell_slice: Slice) -> "VmCont":
        tag = cell_slice.preload_bits(6).to01()
        if tag[:2] == '00':
            return cls('vmc_std', cdata=VmControlData.deserialize(cell_slice), code=VmCellSlice.deserialize(cell_slice))
        elif tag[:2] == '01':
            return cls('vmc_envelope', cdata=VmControlData.deserialize(cell_slice), next=cls.deserialize(cell_slice.load_ref()))
        elif tag[:4] == '1000':
            return cls('vmc_quit', exit_code=cell_slice.load_int(32))
        elif tag[:4] == '1001':
            return cls('vmc_quit_exc')
        elif tag[:5] == '10100':
            return cls('vmc_repeat', count=cell_slice.load_uint(63), body=cls.deserialize(cell_slice.load_ref()), after=cls.deserialize(cell_slice.load_ref()))
        elif tag[:6] == '110000':
            return cls('vmc_until', body=cls.deserialize(cell_slice.load_ref()), after=cls.deserialize(cell_slice.load_ref()))
        elif tag[:6] == '110001':
            return cls('vmc_again', body=cls.deserialize(cell_slice.load_ref()))
        elif tag[:6] == '110010':
            return cls('vmc_while_cond', cond=cls.deserialize(cell_slice.load_ref()), body=cls.deserialize(cell_slice.load_ref()), after=cls.deserialize(cell_slice.load_ref()))
        elif tag[:6] == '110011':
            return cls('vmc_while_body', cond=cls.deserialize(cell_slice.load_ref()), body=cls.deserialize(cell_slice.load_ref()), after=cls.deserialize(cell_slice.load_ref()))
        elif tag[:4] == '1111':
            return cls('vmc_pushint', value=cell_slice.load_int(32), next=cls.deserialize(cell_slice.load_ref()))


class VmControlData:
    """
    vm_ctl_data$_ nargs:(Maybe uint13) stack:(Maybe VmStack) save:VmSaveList
    cp:(Maybe int16) = VmControlData;
    """
    def __init__(self, type_, **kwargs):
        self.type_ = type_
        for k, v in kwargs.items():
            setattr(self, k, v)

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


class VmSaveList:
    """
    _ cregs:(HashmapE 4 VmStackValue) = VmSaveList;
    """
    @classmethod
    def deserialize(cls, cell_slice: Slice) -> "VmSaveList":
        return cell_slice.load_dict(4)
