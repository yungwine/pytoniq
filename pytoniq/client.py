import typing
import ipaddress
import requests

from .adnl.client_tcp import AdnlClientTcp


class LsClientException(BaseException):
    pass


class LsClient:

    def __init__(self,
                 config=typing.Union[dict, str],  # config url or dict
                 ls_index: int = 0):

        if isinstance(config, str):
            config = requests.get(url=config).json()

        if isinstance(config, dict):
            ls = config['liteservers'][ls_index]
            host = str(ipaddress.IPv4Address(ls['ip']))
            port = ls['port']
            pub_key = ls['id']['key']
            if not ls['id']['@type'] == 'pub.ed25519':
                raise LsClientException('unknown pub key type')

            self.adnl = AdnlClientTcp()
