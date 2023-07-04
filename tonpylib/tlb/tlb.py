from abc import ABC, abstractmethod

from ..boc.slice import Slice


class TlbError(BaseException):
    pass


class TlbScheme(ABC):
    """
    This is not the same as TlbSchema in generator.py!
    """
    @staticmethod
    @abstractmethod
    def serialize(*args): ...

    @classmethod
    @abstractmethod
    def deserialize(cls, *args): ...

