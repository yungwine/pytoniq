import time


def generate_query_id(offset: int = 7200):
    return int(time.time() + offset) << 32


def generate_wallet_id(
        wallet_id: int,
        wc: int = 0,
        wallet_version: int = 0,
        network_global_id: int = -239,
) -> int:
    """
    Generates a wallet ID based on global ID, workchain, wallet version, and wallet id.

    :param wallet_id: The subwallet ID (16-bit unsigned integer).
    :param wc: The workchain value (8-bit signed integer).
    :param wallet_version: The wallet version (8-bit unsigned integer).
    :param network_global_id: The network global ID (32-bit signed integer).
    """
    ctx = 0
    ctx |= 1 << 31
    ctx |= (wc & 0xFF) << 23
    ctx |= (wallet_version & 0xFF) << 15
    ctx |= (wallet_id & 0xFFFF)

    return ctx ^ (network_global_id & 0xFFFFFFFF)
