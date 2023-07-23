from abc import ABC, abstractmethod


class TlbError(BaseException):
    pass


class TlbScheme(ABC):
    """
    abstract class for Tlb Schemes wrappers
    """
    @abstractmethod
    def serialize(self, *args): ...

    @classmethod
    @abstractmethod
    def deserialize(cls, *args): ...

    def __repr__(self):
        return str(self.__dict__)
        # TODO beautiful repr
