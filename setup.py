import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pytoniq",
    version="0.1.41",
    author="Maksim Kurbatov",
    author_email="cyrbatoff@gmail.com",
    description="TON Blockchain SDK",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages('.', exclude=['tests', 'examples']),
    classifiers=[
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Libraries",
    ],
    url="https://github.com/yungwine/pytoniq",
    python_requires='>=3.9',
    py_modules=["pytoniq"],
    install_requires=[
        "pytoniq-core>=0.1.42",
        "requests>=2.31.0",
        "setuptools>=65.5.1",
    ],
    extras_require={
        'tvm': ['pytvm>=0.0.11'],
    }
)
