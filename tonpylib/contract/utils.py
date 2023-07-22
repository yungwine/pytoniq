import time


def generate_query_id(offset: int = 7200):
    return int(time.time() + offset) << 32


