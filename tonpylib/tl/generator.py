import re
import time
import zlib
import typing
import os
import timeit


class TlSchema:

    def __init__(self, id: typing.Optional[bytes], name: typing.Optional[str], args: dict):
        self._id = id
        self._name = name
        self._args = args

    @property
    def id(self):
        return self._id

    def little_id(self):
        return self._id[::-1]

    @property
    def name(self):
        return self._name

    @property
    def args(self):
        return self._args

    def is_empty(self):
        return True if not self.id or not self.name else False

    @classmethod
    def empty(cls):
        return cls(None, None, {})

    def __repr__(self):
        return f'TL Schema {self._name} №{self._id.hex()} with args {self._args}'
        # return f'TL Schema {self._name} №{self._id.hex()}'


class TlSchemas:

    def __init__(self, schemas: typing.List[TlSchema]):
        self.list: list = schemas
        self.id_map: typing.Dict[bytes, TlSchema] = {}
        self.name_map: typing.Dict[str, TlSchema] = {}
        self.generate_map()
        self.base_types = {  # bytes
            'int': 4,
            'long': 8,
            'int128': 16,
            'int256': 32,
            'string': None,
            'bytes': None,
            'vector': None
        }

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

    def generate_map(self):
        for schema in self.list:
            schema: TlSchema
            if schema.is_empty():
                continue
            self.id_map[schema.id] = schema
            self.name_map[schema.name] = schema

    def serialize(self, schema: TlSchema, data: dict) -> bytes:
        # https://core.telegram.org/mtproto/serialize
        """
        :param schema: TlSchema object
        :param data: {'key': value}
        :return: TL-serialized bytes
        """
        result = schema.little_id()
        for field, type_ in schema.args.items():
            print(schema.name, field, type_)
            value = data[field]
            if type_ in self.base_types:
                byte_len = self.base_types.get(type_)
                if byte_len is not None:
                    if isinstance(value, bytes):
                        result += value[:byte_len][::-1] + b'\x00' * max(0, byte_len - len(value))
                    if isinstance(value, int):
                        result += value.to_bytes(length=byte_len, byteorder='little', signed=True)
                else:
                    if type_ == 'bytes':
                        if isinstance(value, bytes):
                            temp = b''
                            bytes_len = len(value)
                            # print(schema.name, bytes_len, bytes_len, value)
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
                result += self.serialize(self.get_by_name(type_), value)
        return result

    # def serialize_tcp_packet(self, nonce: bytes, data: bytes):



    def __repr__(self):
        return '[' + '\n'.join([i.__repr__() for i in self.list]) + ']'


class TlRegistrator:

    def __init__(self):
        self._re = re.compile(r"\s([^:]+):(\(.+\)|\S+)")

    def register(self, schema: str) -> TlSchema:
        name = schema.split(' ')[0]
        if '#' in name:
            split_name = name.split('#')
            tl_id = bytes.fromhex(split_name[1])
            name = split_name[0]
        else:
            tl_id = self.get_id(schema.strip())
        args = {i: j for i, j in self._re.findall(schema)}
        # print(schema, args)
        return TlSchema(tl_id, name, args)

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
                if not stripped or stripped.startswith('//'):
                    continue
                if ';' not in stripped:
                    temp += stripped
                result.append(self._registrator.register(stripped))
        return result


if __name__ == '__main__':
    s = time.time()
    # print(timeit.timeit('TlGenerator("schemas/lite_api.tl", TlRegistrator()).generate()', globals=globals(), number=1000))
    schemas = TlGenerator('schemas', TlRegistrator()).generate()
    # print(schemas.get_by_name('liteServer.getMasterchainInfo').id.hex())
    print(schemas)
    print(time.time() - s)

    ping = schemas.get_by_name('tcp.ping')
    print(schemas.serialize(ping, {'random_id': b'\x01\x02'}))

    # query = schemas.get_by_name('adnl.message.query')
    # liteserver = schemas.get_by_name('liteServer.query')
    # master = schemas.get_by_name('liteServer.getMasterchainInfo')
    # print(schemas.serialize(master, {}))
    # s = schemas.serialize(liteserver, {'data': schemas.serialize(master, {})})
    # s3 = schemas.serialize(liteserver, {'data': schemas.serialize(master, {})})
    # s2 = schemas.serialize(query, {'query_id': 1234, 'query': schemas.serialize(liteserver, {'data': schemas.serialize(master, {})})})
    # print(s.hex(), s3.hex(), s2.hex())
