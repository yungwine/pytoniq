from abc import ABC, abstractmethod


class TlbError(BaseException):
    pass


class TlbScheme(ABC):
    """
    This is not the same as TlbSchema in generator.py!
    """
    @classmethod
    @abstractmethod
    def serialize(cls, *args): ...

    @classmethod
    @abstractmethod
    def deserialize(cls, *args): ...

    def __repr__(self):
        return str(self.__dict__)
        # TODO beautiful repr
