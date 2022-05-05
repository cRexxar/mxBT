from .matchMeta import MatchMeta
from .enums import *
import copy
import numpy as np

class TickMatch(MatchMeta):
    def __init__(self, sdk) -> None:
        super().__init__(sdk)
        self.__cur_ask_list = []
        self.__cur_bid_list = []

    def create_order(self, symbol, px=0.0, qty=0.0, side='LONG', type='LIMIT', leverage=1):
        '''
        新建订单,根据type值判断开仓和平仓动作
        :param symbol: 订单标的
        :param px: 订单价格
        :param qty: 订单数量
        :param side: 订单方向
        :param type: 订单类型
        :param leverage: 杠杆
        return {'code': code, 'msg': code_info, 'data': order_info}
        '''
        if symbol != self._symbol:
            return self._format_return(code=Code.PARAMS_ERROR.value, data=symbol)
        if side == Side.LONG.name or side == Side.SHORT.name:
            res = self._newOrder(px=px, qty=qty, side=Side[side].value, action='open', type=type, leverage=leverage)
        else:
            res = self._newOrder(px=px, qty=qty, side=Side[side].value, action='close', type=type, leverage=1)

        # 如果当前订单下单成功,则与当前订单账簿进行撮合
        if res['code'] == Code.SUCCESS.value:
            self._one_side_open_orders_match(open_ids=[res['data']['order_id']])
        return res

    def _one_side_open_orders_match(self, open_ids)->list:
        '''
        单一方向未成交订单进行撮合,
        '''
        __trade_order_pairs = []
        __direction = None
        for id in open_ids:
            __cur_order = self._orders[id]
            if not __direction:
                __direction = __cur_order['side']
            res = self._match(__cur_order)
            # 若单个订单撮合成功,添加进__trade_order_pairs进行统一仓位和账户更新
            if res['code'] == Code.SUCCESS.value:
                __trade_order_pairs.append((id, res['data']['trade_id']))
            __cur_order_book = self.__cur_ask_list if __direction == 'LONG' else self.__cur_bid_list
            if len(__cur_order_book) == 0:
                break
        
        # 统一仓位和账户更新
        self._union_update_position_balance(__trade_order_pairs)
    
    def _match(self, order):
        '''
        单一订单与订单簿匹配
        '''
        __cur_order = copy.deepcopy(order)
        __order_id = __cur_order['order_id']
        __side = __cur_order['side']

        # 限价单当前价位比较符号和对应匹配订单簿设置
        if __side == 'LONG':
            __compare_sign = '>'
            orderbook = self.__cur_ask_list
        else:
            __compare_sign = '<'
            orderbook = self.__cur_bid_list

        if len(orderbook):
            # 临时变量存储成交量,未成交量和成交金额
            __trade_qty = __cur_order['f_qty']
            __untrade_qty = __cur_order['u_qty']
            __trade_capital = 0.0
            for i in range(len(orderbook)):
                if __untrade_qty == 0.0:    # 无未成交量
                    break
                    
                # 当前订单簿价量
                __cur_level_price = orderbook[i][0]
                __cur_level_qty = orderbook[i][1]

                # 限价单情况下,当前价格不满足订单价格要求
                if __cur_order['type'] == OrderType.LIMIT.value and eval(str(__cur_level_price) + __compare_sign + str(__cur_order['px'])):
                    break

                __cur_available_vol = min(__untrade_qty, __cur_level_qty)                       # 当前可成交量
                orderbook[i][1] = self._format_data(orderbook[i][1] - __cur_available_vol)      # 更新订单簿
                __trade_qty += __cur_available_vol                                              # 更新成交量
                __untrade_qty -= __cur_available_vol                                            # 更新未成交量
                __trade_capital += __cur_level_price * __cur_available_vol                      # 更新成交额
                self._set_cur_trade_price(__cur_level_price)                                    # 更新市价

            __untrade_qty = self._format_data(__untrade_qty)
            __trade_qty = self._format_data(__trade_qty)

            # 市价单情况下仍有未成交量则返回错误
            if __cur_order['type'] == OrderType.MARKET.value and __untrade_qty > 0.0:
                return {
                    'code': Code.MAXVALUE_ERROR,
                    'msg': CODEINFO[Code.MAXVALUE_ERROR],
                    'data': __cur_order
                }

            # 更新订单簿
            orderbook = np.array([item for item in orderbook if item[1] > 0.0])
            if __side == 'LONG':
                self.__cur_ask_list = orderbook
            else:
                self.__cur_bid_list = orderbook

            # 若有成交量, 更新原始订单
            if __trade_capital != 0.0:
                __prev_trade_capital = __cur_order['f_px'] * __cur_order['f_qty']
                __delta_trade_qty = __trade_qty - __cur_order['f_qty']
                __cur_order['f_qty'] = __trade_qty
                __cur_order['u_qty'] = __untrade_qty
                __cur_order['u_time'] = self._last_data_timestamp
                __cur_order['f_px'] = self._format_data((__prev_trade_capital + __trade_capital) / __trade_qty)
                __fee = self._format_data(__trade_capital * self._fee)
                __cur_order['fee'] += __fee

                if __untrade_qty == 0.0:
                    __cur_order['status'] = OrderStatus.FILLED.value
                    self._open_orders[__side].remove((__order_id, __cur_order['px']))
                else:
                    __cur_order['status'] = OrderStatus.PARTIALLY_FILLED.value
                self._orders[__order_id] = __cur_order

                self._trade_id += 1
                __trade_order = {
                    'trade_id': self._trade_id,
                    'symbol': self._symbol,
                    'side': __side,
                    'f_amt': __trade_capital,
                    'f_px': self._format_data(__trade_capital / __delta_trade_qty),
                    'f_qty': __delta_trade_qty,
                    'action': __cur_order['action'],
                    'leverage': __cur_order['leverage'],
                    'fee': __fee,
                    'c_time': self._last_data_timestamp
                }
                self._trade_orders[self._trade_id] = __trade_order
                self._tradesLog(__trade_order)

                return self._format_return(data=__trade_order)
            else:
                return {
                    'code': Code.MAXVALUE_ERROR,
                    'msg': CODEINFO[Code.MAXVALUE_ERROR.value],
                    'data': __cur_order
                }
        else:
            return {
                    'code': Code.MAXVALUE_ERROR,
                    'msg': CODEINFO[Code.MAXVALUE_ERROR],
                    'data': __cur_order
                }

    def iteration(self):
        '''
        行情更新时,更新市价,匹配未成交订单
        '''
        __depth = self._sdk.getDepth()
        self._last_data_timestamp = self._sdk.getTs()
        self._set_cur_trade_price((__depth[0][0][0] + __depth[1][0][0]) / 2)
        self.__cur_bid_list, self.__cur_ask_list = __depth[0], __depth[1]
        self._open_orders_match()

    def _tradesLog(self, order):
        action = order['action']
        side = order['side']
        if action=='close':
            side = 'LONG' if order['side']=='SHORT' else 'SHORT'
        content = f"{self._sdk.getTime()} Deal Match|{self._symbol} {action.upper()}_{side} {order['f_px']} {order['f_qty']}"
        self._sdk._log.write(content)