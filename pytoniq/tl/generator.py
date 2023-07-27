import logging
import re
import zlib
import typing
import os


logger = logging.getLogger(name='TL')


class TlError(BaseException):
    pass


class TlSchema:

    def __init__(self, id: typing.Optional[bytes], name: typing.Optional[str], class_name: typing.Optional[str], args: dict) -> None:
        self._id: bytes = id
        self._name: str = name
        self._class_name: str = class_name
        self._args: typing.Dict[str, str] = args  # {'param_name': 'param_type'}

    @property
    def id(self) -> bytes:
        return self._id

    def little_id(self) -> bytes:
        return self._id[::-1]

    @property
    def name(self) -> str:
        return self._name

    @property
    def class_name(self) -> str:
        return self._class_name

    @property
    def boxed(self) -> bool:
        return self._boxed

    @boxed.setter
    def boxed(self, is_boxed: bool):
        self._boxed = is_boxed

    @property
    def args(self) -> typing.Dict[str, str]:
        return self._args

    def is_empty(self) -> bool:
        return True if not self.id or not self.name else False

    @classmethod
    def empty(cls) -> "TlSchema":
        return cls(None, None, None, {})

    def __repr__(self) -> str:
        return f'TL Schema {self._name} №{self._id.hex()} with args {self._args}'
        # return f'TL Schema {self._name} №{self._id.hex()}'


class TlSchemas:

    base_types = {  # bytes len
        'Bool': 4,
        '#': 4,
        'int': 4,
        'long': 8,
        'int128': 16,
        'int256': 32,
        'string': None,
        'bytes': None,
        'vector': None,
    }

    def __init__(self, schemas: typing.List[TlSchema]):
        self.list: list = schemas
        self.id_map: typing.Dict[bytes, TlSchema] = {}
        self.name_map: typing.Dict[str, TlSchema] = {}
        self.class_name_map: typing.Dict[str, typing.List[TlSchema]] = {}
        self.generate_map()

    def get_by_id(self, tl_id: typing.Union[bytes, int], byteorder: typing.Literal['little', 'big'] = 'big') -> TlSchema:
        """
        :param tl_id: id of TL schema
        :param byteorder: provided bytes or int order. if big nothing will happen, if little no matter int or bytes they will be converted
        :return: TlSchema or None
        """
        if isinstance(tl_id, bytes):
            if byteorder == 'little':
                tl_id = tl_id[::-1]
        if isinstance(tl_id, int):
            tl_id = tl_id.to_bytes(4, byteorder)
        return self.id_map.get(tl_id, None)  # or TlSchema.empty()?

    def get_by_name(self, name: str) -> TlSchema:
        """
        :param name: name of TL Schema
        :return: TlSchema or None
        """
        return self.name_map.get(name, None)  # or TlSchema.empty()?

    def get_by_class_name(self, class_name: str) -> typing.List[TlSchema]:
        """
        :param class_name: boxed class_name of TL Schema
        :return: TlSchema or None
        """
        return self.class_name_map.get(class_name, None)  # or TlSchema.empty()?

    def generate_map(self):
        for schema in self.list:
            schema: TlSchema
            if schema.is_empty():
                continue
            self.id_map[schema.id] = schema
            self.name_map[schema.name] = schema
            self.class_name_map[schema.class_name] = self.class_name_map.get(schema.class_name, []) + [schema]

    def serialize_field(self, type_: str, value):
        logger.log(level=5, msg=f'serializing {type_} with value {value}')
        result = b''
        if type_ in self.base_types:
            byte_len = self.base_types.get(type_)
            if byte_len:
                if isinstance(value, bool):
                    if value:
                        result += b'\xb5ur\x99'  # booltrue
                    else:
                        result += b'7\x97y\xbc'  # boolfalse
                elif isinstance(value, bytes):
                    result += value[:byte_len][::-1] + b'\x00' * max(0, byte_len - len(value))
                elif isinstance(value, int):
                    result += value.to_bytes(length=byte_len, byteorder='little', signed=True)
                elif isinstance(value, str):
                    result += bytes.fromhex(value)
            else:
                if type_ == 'bytes':
                    if isinstance(value, bytes):
                        temp = b''
                        bytes_len = len(value)
                        if bytes_len <= 253:
                            temp += bytes_len.to_bytes(length=1, byteorder='little')
                        else:
                            temp += b'\xFE' + bytes_len.to_bytes(length=3, byteorder='little')
                        temp += value
                        if len(temp) % 4:
                            temp += (4 - len(temp) % 4) * b'\x00'
                        result += temp
                    else:
                        pass  # TODO
        else:
            schema = self.get_by_class_name(type_)
            if schema:  # implicit
                if len(schema) == 1:
                    result += self.serialize(schema[0], value, boxed=True)
                else:
                    result += value  # should be already in bytes, otherwise how do serializer know what scheme it should serialize?
            else:  # explicit
                if type_.startswith('('):
                    subtype = type_.split()[1][:-1]
                    if 'vector' in type_:
                        temp = len(value).to_bytes(4, 'little', signed=False)
                        for v in value:
                            temp += self.serialize_field(subtype, v)
                        result += temp
                else:
                    result += self.serialize(self.get_by_name(type_), value, boxed=False)
        return result

    def serialize(self, schema: TlSchema, data: dict, boxed: bool = True) -> bytes:
        logger.log(level=5, msg=f'serializing schema {schema}')
        # https://core.telegram.org/mtproto/serialize
        """
        :param schema: TlSchema object
        :param data: {'key': value} - data to serialize
        :param boxed: need TL id prefix?
        :return: TL-serialized bytes
        """
        if boxed:
            result = schema.little_id()
        else:
            result = b''
        for field, type_ in schema.args.items():
            if 'mode' in type_ or 'flags' in type_:
                type_ = type_.split('?')[1]
                if data.get(field) is None:
                    continue
            value = data[field]
            result += self.serialize_field(type_, value)
            # p = self.serialize_field(type_, value)
            # print(field, type_, len(p), p.hex())
        return result

    def deserialize(self, data: bytes, boxed: bool = True, args=None) -> typing.Tuple[typing.Union[dict, bytes], int]:
        i = 0
        result = {}
        if boxed:
            schema = self.get_by_id(data[i:i + 4], 'little')
            if not schema:  # is None
                return data, len(data)
                # return {'bytes': data}, len(data)
            i += 4
            args = schema.args
        logger.log(level=5, msg=f'deserializing schema with args {args}')
        for field, type_ in args.items():
            if '?' in type_:
                index = int(type_[type_.find('.') + 1: type_.find('?')])
                mask = bin(result.get('mode')).replace('0b', '')[::-1]
                if index >= len(mask):
                    continue
                if mask[index] == '0':
                    continue
                type_ = type_.split('?')[-1]

            if type_ in self.base_types:
                byte_len = self.base_types.get(type_)
                if byte_len:  # is not None
                    if type_ == 'Bool':
                        if data[i:i + byte_len] == b'\xb5ur\x99':
                            result[field] = True
                        elif data[i:i + byte_len] == b'7\x97y\xbc':
                            result[field] = False
                    elif type_ in ('int128', 'int256'):
                        result[field] = data[i:i + byte_len].hex()
                    else:
                        result[field] = int.from_bytes(data[i:i + byte_len], 'little', signed=True)
                    i += byte_len
                else:
                    if type_ in ('bytes', 'string'):
                        if data[i:i+1] == b'\xFE':
                            # b'\xFE' means data len took more than one byte
                            byte_len = int.from_bytes(data[i+1:i+4], 'little')
                            attach_len = 4
                            i += 4
                        else:
                            attach_len = 1
                            byte_len = int.from_bytes(data[i:i+1], 'little')
                            i += 1
                        result[field], _ = self.deserialize(data[i:i+byte_len])
                        i += byte_len
                        if (byte_len + attach_len) % 4:
                            i += 4 - (byte_len + attach_len) % 4
                        if type_ == 'string':
                            result[field] = result[field].decode()
            else:
                # stucks when errors # TODO
                if type_.startswith('('):
                    subtype = type_.split()[1][:-1]
                    sch = self.get_by_name(subtype)

                    # result[field], j = self.deserialize(data[i:], False, sch.args)
                    if 'vector' in type_:
                        length = int.from_bytes(data[i:i + 4], 'little', signed=False)
                        i += 4
                        result[field] = []
                        for _ in range(length):
                            if sch:
                                deser, j = self.deserialize(data[i:], False, sch.args)
                            else:
                                deser, j = self.deserialize(data[i:], True)

                            result[field].append(deser)
                            i += j
                else:
                    sch = self.get_by_name(type_)
                    if not sch:
                        # sch = self.get_by_class_name(type_)
                        id = data[i:i + 4][::-1]
                        sch = self.get_by_id(id)
                        i += 4
                    result[field], j = self.deserialize(data[i:], False, sch.args)
                    i += j
        return result, i

    def __repr__(self):
        return '[' + '\n'.join([i.__repr__() for i in self.list]) + ']'


def split(fields: str):
    result = {}
    temp = ''
    temp_key = ''
    br = 0
    for l in fields:
        if l == '(':
            temp += l
            br += 1
            continue
        if l == ')':
            temp += l
            br -= 1
            continue
        if l == ':':
            temp_key = temp
            temp = ''
            continue
        if l == ' ':
            if br == 0:
                if temp_key:
                    result[temp_key] = temp
                temp_key = ''
                temp = ''
            else:
                temp += l
            continue
        temp += l
    return result


class TlRegistrator:

    def __init__(self):
        self._re = re.compile(r"\s([^:]+):(\(.+\)|\S+)")
        self._base_types = TlSchemas.base_types
        # https://www.debuggex.com/r/kT4s0-gThkHLZCGO ; to avoid recursion in reg ex and use built-in "re" lib.
        # self._re = re.compile(r'[\w]*[^\w\s]*\[[^\]]*\]|'
        #                             r'[\w]*[^\w\s]*\([^)(]*(?:\([^)(]*(?:\([^)(]*(?:\([^)(]*\)[^)(]*)*\)[^)(]*)*\)[^)(]*)*\)|'
        #                             r'[\w]*[^\w\s]*\{[^\}]*\}|'
        #                             r'\S+')

    def _is_boxed(self, args: dict) -> bool:
        for type_ in args.values():
            if type_ not in self._base_types:
                return True
        return False

    def register(self, schema: str) -> TlSchema:
        schema = schema.split('//')[0]
        name = schema.split(' ')[0]
        if '#' in name:
            split_name = name.split('#')
            tl_id = bytes.fromhex(split_name[1])
            name = split_name[0]
        else:
            tl_id = self.get_id(schema.strip())
        # args = {i: j for i, j in self._re.findall(schema)}
        args = split(' '.join(schema.split()[1:-1]))
        class_name = schema.split(' ')[-1].replace(';', '')
        return TlSchema(tl_id, name, class_name, args)

    @staticmethod
    def clear(schema: str) -> str:
        return schema.replace(';', '').replace('(', '').replace(')', '')

    @staticmethod
    def crc32(schema: str) -> int:
        return zlib.crc32(schema.encode())

    def get_id(self, schema: str) -> bytes:
        return self.crc32(self.clear(schema)).to_bytes(4, 'big')

    def get_params(self, schema: str) -> dict:
        pass


class TlGenerator:
    """
    This part is not really optimized because this will run only once when initialize client and 1000 runs took about 0.3 sec on 4 cores CPU
    So the best decision was to make code readable instead of well optimized and difficult-to-understand
    """
    def __init__(self, path: str, registrator: typing.Optional[TlRegistrator] = None) -> None:
        self._path = os.path.normpath(path)
        if registrator is None:
            registrator = TlRegistrator()
        self._registrator = registrator

    def generate(self):
        result = []
        if os.path.isdir(self._path):
            for f in os.listdir(self._path):
                result += self.from_file(os.path.join(self._path, f))
        else:
            result = self.from_file(self._path)
        return TlSchemas(result)

    def from_file(self, file_path: str):
        result = []
        with open(file_path, 'r') as f:
            temp = ''
            for line in f:
                stripped = line.strip()

                if not stripped or stripped.startswith('//') or stripped.startswith('---'):
                    continue
                if ';' not in stripped:
                    temp += stripped + ' '
                    continue
                else:
                    stripped = temp + stripped
                    temp = ''
                result.append(self._registrator.register(stripped))
        return result

