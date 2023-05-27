from tonpylib.adnl.client_tcp import AdnlClientTcp


host = '65.21.141.231'
port = 17728

pub_key_b64 = 'BYSVpL7aPk0kU5CtlsIae/8mf2B/NrBi7DKmepcjX6Q='

client = AdnlClientTcp(
    host,
    port,
    pub_key_b64
)

if __name__ == '__main__':
    client.connect()
