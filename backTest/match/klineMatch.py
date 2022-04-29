from .matchMeta import MatchMeta
from .enums import *
import copy
import numpy as np

class KlineMatch(MatchMeta):
    __cur_bar = None

    def __init__(self, sdk) -> None:
        super().__init__(sdk)
        self.__volume_threshold = self._sdk._config['volumeThreshold'] if 'volumeThreshold' in self._sdk._config.keys() else .5

    def iteration(self):
        '''
        行情更新时
        '''
        self.__cur_bar = self._sdk.getKline()
        self._set_cur_trade_price(self.__cur_bar[4])
        self._last_data_timestamp = self.__cur_bar[0]
        self._open_orders_match()

    def create_order(self, symbol, px=0, qty=0, side='LONG', type='LIMIT', leverage=1):
        if symbol != self._symbol:
            return self._format_return(code=Code.PARAMS_ERROR.value, data=symbol) 
        if side == Side.LONG.name or side == Side.SHORT.name:
            res = self._newOrder(px=px, qty=qty, side=Side[side].value, action='open', type=type, leverage=leverage)
        else:
            res = self._newOrder(px=px, qty=qty, side=Side[side].value, action='close', type=type, leverage=1)

        return res

    def _match(self, order):
        __cur_order = copy.deepcopy(order)
        __order_id = __cur_order['order_id']

        __tradable_volume = self.__cur_bar[5] * self.__volume_threshold
        __cur_open_price = self.__cur_bar[2]
        
        if __cur_order['type'] == OrderType.MARKET.value and __tradable_volume < __cur_order['u_qty']:
            return {
                    'code': Code.MAXVALUE_ERROR,
                    'msg': CODEINFO[Code.MAXVALUE_ERROR],
                    'data': __cur_order
                }
        __cur_f_px = 0.0
        if __cur_order['type'] == OrderType.LIMIT.value:
            if __cur_order['side'] == Side.LONG.value:
                __cur_low_price = self.__cur_bar[3]
                if __cur_order['px'] >= __cur_open_price:
                    __cur_f_px = __cur_open_price
                elif __cur_order['px'] < __cur_open_price and __cur_order['px'] >= __cur_low_price:
                    __cur_f_px = __cur_order['px']
            
            if __cur_order['side'] == Side.SHORT.value:
                __cur_high_price = self.__cur_bar[1]
                if __cur_order['px'] <= __cur_open_price:
                    __cur_f_px = __cur_open_price
                elif __cur_order['px'] > __cur_open_price and __cur_order['px'] <= __cur_high_price:
                    __cur_f_px = __cur_order['px']
        else:
            __cur_f_px = __cur_open_price

        if __cur_f_px:
            __available_volume = min(__tradable_volume, __cur_order['u_qty'])
            __trade_amt = __cur_f_px * __available_volume
            __cur_order['f_qty'] += __available_volume
            __cur_order['u_qty'] -= __available_volume
            __cur_order['f_px'] = (__cur_order['f_px'] * __cur_order['f_qty'] + __trade_amt) / __cur_order['f_qty']
            __cur_order['u_time'] = self._last_data_timestamp
            __cur_order['fee'] += __trade_amt * self._fee


            if __cur_order['u_qty'] == 0.0:
                __cur_order['status'] = OrderStatus.FILLED.value
                self._open_orders[__cur_order['side']].remove((__order_id, __cur_order['px']))
            else:
                __cur_order['status'] = OrderStatus.PARTIALLY_FILLED.value

            self._orders[__order_id] = __cur_order

            self._trade_id += 1
            __trade_order = {
                'trade_id': self._trade_id,
                'symbol': self._symbol,
                'side': __cur_order['side'],
                'f_amt': __trade_amt,
                'f_px': __cur_f_px,
                'f_qty': __available_volume,
                'action': __cur_order['action'],
                'leverage': __cur_order['leverage'],
                'fee': __trade_amt * self._fee,
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



    def _one_side_open_orders_match(self, open_ids) -> list:
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
        
        # 统一仓位和账户更新
        self._union_update_position_balance(__trade_order_pairs)

    
