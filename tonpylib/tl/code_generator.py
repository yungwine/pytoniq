# from .generator import TlGenerator, TlEncoder
import time
import timeit

from generator import TlGenerator, TlRegistrator, TlSchemas


class TagsGenerator:

    def __init__(self, tl_generator: TlGenerator, file_name: str):
        self._schemas: TlSchemas = tl_generator.generate()
        self._code = '\nclass TlTags:\n'
        self._file_name = file_name

    def generate(self):
        for name, schema in self._schemas.name_map.items():
            if '---' in name:
                continue
            self._code += f'\t{name.replace(".", "_")} = {schema.id}\n'
        with open(self._file_name, 'w') as f:
            f.write(self._code)


if __name__ == '__main__':
    s = time.time()
    # print(timeit.timeit('TlGenerator("schemes/lite_api.tl", TlEncoder()).generate()', globals=globals(), number=1000))
    my_tl_generator = TlGenerator('schemas/lite_api.tl', TlRegistrator())
    TagsGenerator(my_tl_generator, 'new_tags.py').generate()
    print(time.time() - s)
