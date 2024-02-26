def gen_json_response(data=None, code=200, msg='ok', msg_key='msg', code_key='code', data_key='data', extends={}):

    res_data = {
        code_key: code,
        msg_key: msg,
        **extends
    }
    if data is not None:
        res_data[data_key] = data
    return res_data