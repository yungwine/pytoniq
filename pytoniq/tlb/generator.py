"""
WIP
"""
import os
import re
import typing

from bitarray import bitarray
from bitarray.util import hex2ba

from pytoniq.boc.slice import Slice


class TlbGeneratorError(BaseException):
    pass


class TlbDeserializatorError(BaseException):
    pass


class TlbSchema:

    def __init__(self, class_name: str, class_args: list, fields: dict, constructor_name: str, tag: bitarray):
        self._class_name = class_name
        self._class_args = class_args
        self._fields = fields
        self._constructor_name = constructor_name
        self._tag = tag

    @property
    def constructor_name(self) -> str:
        return self._constructor_name

    @property
    def class_name(self) -> str:
        return self._class_name

    @property
    def class_args(self) -> list:
        return self._class_args

    @property
    def tag(self) -> bitarray:
        return self._tag

    @property
    def fields(self) -> typing.Dict[str, str]:
        return self._fields

    def parse_class_args(self):
        pass

    def __repr__(self):
        return f'<TlbSchema#{self._tag.tobytes().hex() if self._tag else "_"} {self._class_name} {"".join(self._class_args)} with fields {self._fields}>'
        # return f'<TlbSchema#{self._tag.tobytes().hex() if self._tag else "_"} {self._class_name} {"".join(self._class_args)}>'


class TlbSchemas:

    def __init__(self, schemas: typing.List[TlbSchema]) -> None:
        self._list: typing.List[TlbSchema] = schemas
        self.class_name_map: typing.Dict[str, typing.List[TlbSchema]] = {}
        self._lexer = Lexer()
        self.generate_map()

    def append(self, sch: TlbSchema) -> None:
        self._list.append(sch)
        self.class_name_map[sch.class_name] = self.class_name_map.get(sch.class_name, []) + [sch]

    def generate_map(self) -> None:
        for schema in self._list:
            self.class_name_map[schema.class_name] = self.class_name_map.get(schema.class_name, []) + [schema]

    def get_by_class_name(self, class_name: str) -> typing.List[TlbSchema]:
        return self.class_name_map.get(class_name)

    @staticmethod
    def _is_int(num: str):
        try:
            int(num)
            return True
        except:
            return False

    @staticmethod
    def _is_eq(param: str) -> bool:
        if '+' in param or '-' in param:
            return True
        return False

    @staticmethod
    def _solve_eq(equation: str, result: int) -> int:
        return None
        # return solve(f'Eq({equation}, {result})')[0]

    @staticmethod
    def _find_var(equation: str) -> typing.Optional[str]:
        for i in equation:
            if i.isalpha():
                return i

    def _find_by_class_args(self, schemas: typing.List[TlbSchema], vars_: list):
        """
        for every possible variant we assign points, and we choose the variant with the max points
        """
        max_point = -1
        best_schema = None
        for sch in schemas:
            cur_point = 0
            if len(sch.class_args) != len(vars_):
                continue
            for i in range(len(sch.class_args)):
                if self._is_int(sch.class_args[i]):
                    if sch.class_args[i] == str(vars_[i]):
                        cur_point += 1
                    else:
                        cur_point -= 1
                elif self._is_eq(sch.class_args[i]):
                    print('eq found: ', sch)
                    # TODO
                    pass
            if cur_point > max_point:
                max_point = cur_point
                best_schema = sch
        if best_schema is None:
            raise TlbDeserializatorError('couldn\'t find fit schema')
        return best_schema

    @staticmethod
    def _compare_by_bit_prefix(cell: Slice, tag: bitarray) -> bool:
        print('comparing', cell.preload_bits(len(tag)), tag)
        return cell.preload_bits(len(tag)) == tag

    def deserialize_field(self, cell_slice: Slice, type_: str, args: dict = {}):
        if type_ == 'Cell':
            return cell_slice
        elif 'bits' in type_:
            return cell_slice.load_bits(int(type_.split('bits')[-1]))
        elif 'int' in type_:
            return cell_slice.load_int(int(type_.split('int')[-1]))
        elif 'uint' in type_:
            return cell_slice.load_uint(int(type_.split('uint')[-1]))
        elif type_.startswith('(##'):                      # (## number)
            return cell_slice.load_uint(int(type_[4:-1]))  # 0123number-1
        elif type_.startswith('(#<='):
            pass  # TODO
        elif type_.startswith('(') and type_.endswith(')'):
            # dict:(HashmapE 32 (VarUInteger 32))
            # stack:(VmStackList depth)
            type_ = type_[1:-1]
            type_ = self._lexer.split(type_)
            type_, class_args = type_[0], type_[1:]
            for i in range(len(class_args)):
                if class_args[i] in args:
                    class_args[i] = args[class_args[i]]
            return self.deserialize(cell_slice, type_, class_args)
        elif type_.startswith('^'):
            return self.deserialize_field(cell_slice.load_ref(), type_[1:], args)
        else:
            return self.deserialize(cell_slice, type_, [])

    def deserialize(self, cell_slice: Slice, class_name: str, class_args: list):
        """
        class_args id dict where keys are indexes or names of arguments and values are arguments values
        for e.g. we have VmStackList
        """
        schemas = self.get_by_class_name(class_name)
        res_schemas = []
        if len(schemas) > 1:  # if we have many possible schemas we compare by tag
            for sch in schemas:
                if self._compare_by_bit_prefix(cell_slice, sch.tag):
                    res_schemas.append(sch)
            schemas = res_schemas
        if len(schemas) > 1:  # if we still have many possible schemas we compare by class arguments
            schemas = [self._find_by_class_args(schemas, class_args)]
        schema = schemas[0]
        if schema.tag:
            cell_slice.load_bits(len(schema.tag))

        result = {}

        for i in range(len(schema.class_args)):
            arg = schema.class_args[i]
            if self._is_eq(arg):
                result[self._find_var(arg)] = self._solve_eq(arg, class_args[i])

        for field, type_ in schema.fields.items():
            result[field] = self.deserialize_field(cell_slice, type_, result)
            continue
            if type_ == 'Cell':
                result[field] = cell_slice
            elif 'bits' in type_:
                result[field] = cell_slice.load_bits(int(type_.split('bits')[-1]))
            elif 'int' in type_:
                result[field] = cell_slice.load_int(int(type_.split('int')[-1]))
            elif 'uint' in type_:
                result[field] = cell_slice.load_uint(int(type_.split('uint')[-1]))
            elif type_.startswith('(##'):                         # (## number)
                result[field] = cell_slice.load_uint(int(type_[4:-1]))  # 0123number-1
            elif type_.startswith('(#<='):
                pass   # TODO
            elif type_.startswith('(') and type_.endswith(')'):
                # dict:(HashmapE 32 (VarUInteger 32))
                # stack:(VmStackList depth)
                type_ = type_[1:-1]
                type_ = self._lexer.split(type_)
                type_, args = type_[0], type_[1:]
                for i in range(len(args)):
                    if args[i] in result:
                        args[i] = result[args[i]]
                result[field] = self.deserialize(cell_slice, type_, args)
            elif type_.startswith('^'):
                result[field] = self.deserialize(cell_slice.load_ref(), type_[1:], class_args)
        return result


class Lexer:

    def __init__(self):
        self._tag_hex = re.compile(r'#([0-9a-f]+_?|_)')
        self._tag_bin = re.compile(r'\$([01]*_?)')
        # https://www.debuggex.com/r/kT4s0-gThkHLZCGO ; to avoid recursion in reg ex and use built-in "re" lib.
        self._splitter = re.compile(r'[\w]*[^\w\s]*\[[^\]]*\]|'
                                    r'[\w]*[^\w\s]*\([^)(]*(?:\([^)(]*(?:\([^)(]*(?:\([^)(]*\)[^)(]*)*\)[^)(]*)*\)[^)(]*)*\)|'
                                    r'[\w]*[^\w\s]*\{[^\}]*\}|'
                                    r'\S+')

    def detect_tag(self, constructor: str) -> typing.Tuple[str, bitarray]:
        """
        :param constructor: constructor name with tag
        :return: constructor name and tag in bitarray
        """
        # hex_tag = self._tag_hex.findall(constructor)
        # if not hex_tag:
        #     bin_tag = self._tag_bin.findall(constructor)
        #     if not bin_tag:
        #         return constructor, bitarray('')
        #     return bitarray(bin_tag[0])
        # return hex2ba(hex_tag[0], 'big')
        if '#' in constructor:
            cons_name, tag = constructor.split('#')
            tag = tag.replace('_', '')
            return cons_name, hex2ba(tag, 'big')
        if '$' in constructor:
            cons_name, tag = constructor.split('$')
            tag = tag.replace('_', '')
            return cons_name, bitarray(tag)
        return constructor, bitarray('')  # or crc32? TODO

    def split(self, s: str):
        return self._splitter.findall(s)


class TlbRegistrator:

    def __init__(self):
        self._lexer = Lexer()

    def register(self, schema: str) -> TlbSchema:
        if '=' not in schema:
            raise TlbGeneratorError('can\'t parse tlb schema: expected "=" in schema')
        splited = self._lexer.split(schema.replace(';', ''))
        eq_i = splited.index('=')

        class_name = splited[eq_i + 1]
        class_args = splited[eq_i + 2:]
        fields = self.parse_args(splited[1: eq_i])
        constructor_name, tag = self._lexer.detect_tag(splited[0])

        return TlbSchema(class_name, class_args, fields, constructor_name, tag)

        print('schema: ', schema)
        print('classname: ', class_name)
        print('class args: ', class_args)
        print('constructor name: ', constructor_name)
        print('constructor tag: ', tag)
        print('args: ', fields, '\n\n')

    @staticmethod
    def parse_args(fields: typing.List[str]) -> dict:
        result = {}
        for field in fields:
            if '{' in field or '}' in field:
                continue
            if field.startswith('^'):
                result['_'] = field
                continue
            if ':' not in field:
                name, type_ = '_', field
            else:
                name, type_ = field.split(':', maxsplit=1)
            result[name] = type_
        return result


class TlbGenerator:
    def __init__(self, path: str, registrator: typing.Optional[TlbRegistrator] = None) -> None:
        self._path = os.path.normpath(path)
        if registrator is None:
            registrator = TlbRegistrator()
        self._registrator = registrator

    def generate(self):
        result = []
        if os.path.isdir(self._path):
            for f in os.listdir(self._path):
                if f.endswith('.tlb'):
                    result += self.from_file(os.path.join(self._path, f))
        else:
            result = self.from_file(self._path)
        return TlbSchemas(result)

    def from_file(self, file_path: str):
        result = []
        with open(file_path, 'r') as f:
            temp = ''
            comment = False

            for line in f:
                stripped = line.lstrip()
                if '*/' in stripped:
                    comment = False
                    continue

                if not stripped or stripped.startswith('//') or comment:
                    continue

                if '/*' in stripped:
                    comment = True
                    continue

                if '//' in stripped:
                    stripped = stripped.split('//')[0].strip()

                stripped = stripped.replace('\n', ' ')

                if ';' not in stripped:
                    temp += stripped
                    continue
                else:
                    stripped = temp + stripped
                    temp = ''
                result.append(self._registrator.register(stripped))
                # result.append(stripped)
        return result


if __name__ == '__main__':
    schemas = TlbGenerator('schemas').generate()

    # schemas.deserialize()

    # for i, j in schemas.class_name_map.items():
    #     print(i, j)
