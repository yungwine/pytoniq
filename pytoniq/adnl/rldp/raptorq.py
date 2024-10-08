SYMBOL_SIZE = 768


def _import_raptorq():
    try:
        import pyraptorq
    except ImportError:
        raise ImportError('pyraptorq library is required to use RLDP, use command: `pip install "pytoniq[rldp]"`')


def get_encoder(engine, data: bytes, symbol_size: int):
    _import_raptorq()
    from pyraptorq import Encoder
    return Encoder(data, symbol_size, engine)


def get_decoder(engine, data_len: int, symbol_size: int, symbols_count: int):
    _import_raptorq()
    from pyraptorq import Decoder
    return Decoder(symbols_count, symbol_size, data_len, engine)
