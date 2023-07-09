import typing


class BlockId:
    """
    tonNode.blockId workchain:int shard:long seqno:int = tonNode.BlockId;
    """
    def __init__(self, workchain: int, shard: typing.Optional[int], seqno: int):
        if shard is None:
            shard = -9223372036854775808
        self.workchain = workchain
        self.shard = shard
        self.seqno = seqno

    def to_dict(self):
        return {'workchain': self.workchain, 'shard': self.shard, 'seqno': self.seqno}

    @classmethod
    def from_dict(cls, block_id: dict):
        return cls(workchain=block_id.get('workchain'), shard=block_id.get('shard'), seqno=block_id.get('seqno'))


class BlockIdExt:
    """
    tonNode.blockIdExt workchain:int shard:long seqno:int root_hash:int256 file_hash:int256 = tonNode.BlockIdExt;
    """

    def __init__(self, workchain: int, shard: typing.Optional[int], seqno: int,
                 root_hash: typing.Union[str, bytes], file_hash: typing.Union[str, bytes]):
        if shard is None:
            shard = -9223372036854775808
        if isinstance(root_hash, str):
            root_hash = bytes.fromhex(root_hash)
        if isinstance(file_hash, str):
            file_hash = bytes.fromhex(file_hash)
        self.workchain = workchain
        self.shard = shard
        self.seqno = seqno
        self.root_hash = root_hash
        self.file_hash = file_hash

    def to_dict(self):
        return {'workchain': self.workchain, 'shard': self.shard, 'seqno': self.seqno, 'root_hash': self.root_hash, 'file_hash': self.file_hash}

    @classmethod
    def from_dict(cls, block_id_ext: dict):
        return cls(workchain=block_id_ext.get('workchain'), shard=block_id_ext.get('shard'), seqno=block_id_ext.get('seqno'),
                   root_hash=block_id_ext.get('root_hash'), file_hash=block_id_ext.get('file_hash'))

    def __repr__(self):
        return f'<TL BlockIdExt {self.__dict__} >'
