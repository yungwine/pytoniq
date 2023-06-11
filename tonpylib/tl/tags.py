
class TlTags:

    ping_tag = 0x9a2b084d
    pong_tag = 0x03fb69dc
    adnl_message_answer_tag = 0x1684ac0f
    adnl_message_query_tag = 0x7af98bb4
    bool_false_tag = 0x379779bc
    bool_true_tag = 0xb5757299
    bytes_tag = 0xd1144618
    double_tag = 0x54c11022
    function_tag = 0x97c1cb7a
    int128_tag = 0xb7f7cc84
    int256_tag = 0x5bebed7b
    int_tag = 0xda9b50a8
    lite_server_account_id_tag = 0xc5e2a075
    lite_server_account_state_tag = 0x51c77970
    lite_server_all_shards_info_tag = 0x2de78f09
    lite_server_block_data_tag = 0x6ced74a5
    lite_server_block_header_tag = 0x19822d75
    lite_server_block_link_back_tag = 0xef1b7eef
    lite_server_block_link_forward_tag = 0x1cce0f52
    lite_server_block_state_tag = 0xcdcadab
    lite_server_block_transactions_tag = 0x5c6c542f
    lite_server_config_info_tag = 0x2f277bae
    lite_server_current_time_tag = 0xd0053e9
    lite_server_debug_verbosity_tag = 0x3347405d
    lite_server_error_tag = 0x48e1a9bb
    lite_server_get_account_state_tag = 0x250e896b
    lite_server_get_all_shards_info_tag = 0x6bfdd374
    lite_server_get_block_header_tag = 0x9e06ec21
    lite_server_get_block_proof_tag = 0x449cea8a
    lite_server_get_block_tag = 0x0dcf7763
    lite_server_get_config_all_tag = 0xb7261b91
    lite_server_get_config_params_tag = 0x638df89e
    lite_server_get_masterchain_info_ext_tag = 0xdf71a670
    lite_server_get_masterchain_info_tag = 0x2ee6b589
    lite_server_get_one_transaction_tag = 0xea240fd4
    lite_server_get_shard_info_tag = 0x25f4a246
    lite_server_get_state_tag = 0xb62e6eba
    lite_server_get_time_tag = 0x345aad16
    lite_server_get_transactions_tag = 0xa1e7401c
    lite_server_get_validator_stats_tag = 0xbc581a09
    lite_server_get_version_tag = 0xb942b23
    lite_server_list_block_transactions_tag = 0xdac7fcad
    lite_server_lookup_block_tag = 0x1ef7c8fa
    lite_server_masterchain_info_ext_tag = 0xf5e0cca8
    lite_server_masterchain_info_tag = 0x81288385
    lite_server_partial_block_proof_tag = 0xc1d2d08e
    lite_server_query_prefix_tag = 0x86e6d372
    lite_server_query_tag = 0xdf068c79
    lite_server_run_method_result_tag = 0x6b619aa3
    lite_server_run_smc_method_tag = 0xd25dc65c
    lite_server_send_message_tag = 0x82d40a69
    lite_server_send_msg_status_tag = 0x97e55039
    lite_server_shard_info_tag = 0x84cde69f
    lite_server_signature_set_tag = 0x9755e192
    lite_server_signature_tag = 0x55f8dea3
    lite_server_transaction_id3_tag = 0x77da812c
    lite_server_transaction_id_tag = 0xaf652fb1
    lite_server_transaction_info_tag = 0x47edde0e
    lite_server_transaction_list_tag = 0x9dd72eb9
    lite_server_validator_stats_tag = 0xd896f7b9
    lite_server_version_tag = 0xe591045a
    lite_server_wait_masterchain_seqno_tag = 0x92b8eaba
    long_tag = 0xba6c0722
    object_tag = 0xa04c7029
    string_tag = 0x246e28b5
    ton_node_block_id_ext_tag = 0x78eb5267
    ton_node_block_id_tag = 0x67b1cdb7
    ton_node_zero_state_id_ext_tag = 0xae35721d
    true_tag = 0x39d3ed3f
    vector_tag = 0x144a1a50

    @classmethod
    def in_bytes(cls, tag: int, order: str = 'little'):
        """
        :param tag: tag TL scheme id
        :param order by default all fields of this class are in little endian
        :return tag in bytes representation
        Usage:
        TlTags.in_bytes(Tl.<tl_scheme>)
        """

