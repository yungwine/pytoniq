import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pytoniq",
    version="0.0.6",
    author="Maksim Kurbatov",
    author_email="cyrbatoff@gmail.com",
    description="TON Blockchain SDK",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages('.', exclude=['tests', 'examples', 'pytoniq/adnl']),
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Libraries",
    ],
    url="https://github.com/yungwine/pytoniq",
    python_requires='>=3.10',
    py_modules=["pytoniq"],
    install_requires=[
        "cryptography>=40.0.2",
        "bitarray>=2.6.0",
        "requests>=2.31.0",
        "x25519>=0.0.2",
        "setuptools>=65.5.1",
        "PyNaCl>=1.5.0"
    ]
)
