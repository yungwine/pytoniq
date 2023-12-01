import typing

from .client import LiteClient, LiteClientError, RunGetMethodError, BlockId, BlockIdExt
from .balancer import LiteBalancer, BalancerError

LiteClientLike = typing.Union[LiteClient, LiteBalancer]
