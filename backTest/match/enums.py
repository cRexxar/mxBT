from enum import Enum, unique

CODEINFO = {
    100000: '调用成功, 正常返回数据',
    100001: '调用失败, 未定义错误',
    100002: '网络错误',
    100003: '下单不足最小量',
    100004: '下单超过最大值',
    100005: '参数不合法',
    100006: '下单价格超出限制',
    100007: '请求过于频繁',
    100008: '不允许自成交',
    100009: 'api key 不存在或失效',
    100010: '余额不足, 下单失败',
    100011: '订单不存在',
    100012: '网络超时',
}
@unique
class Code(Enum):
    SUCCESS = 100000
    UNKNOW_ERROR = 100001
    NETWORK_ERROR = 100002
    MINQTY_ERROR = 100003
    MAXVALUE_ERROR = 100004
    PARAMS_ERROR = 100005
    EXCEED_PX_ERROR = 100006
    REQUEST_LIMIT_ERROR = 100007
    SELFTRADE_ERROR = 100008
    API_ERROR = 100009
    FREE_BALANCE_ERROR = 100010
    UNEXIST_ERROR = 100011
    TIMEOUT_ERROR = 100012


@unique
class OrderType(Enum):
    LIMIT = 'LIMIT'
    MARKET = 'MARKET'

@unique
class TimeInForce(Enum):
    GTC = 'GTC'
    IOC = 'IOC'
    FOK = 'FOK'
    POST_ONLY = 'POST_ONLY'

class Side(Enum):
    LONG = 'LONG'
    SHORT = 'SHORT'
    CLOSE_LONG = 'SHORT'
    CLOSE_SHORT = 'LONG'

@unique
class OrderStatus(Enum):
    FAILED = 'FAILED'
    CANCELED = 'CANCELED'
    OPEN = 'OPEN'
    PARTIALLY_FILLED = 'PARTIALLY_FILLED'
    FILLED = 'FILLED'

# print('LIMIT' in OrderType.__members__)