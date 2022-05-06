from .enums import *
from statistics import mean
from operator import itemgetter
from math import inf
import copy
import pandas as pd

class MatchMeta:
    def __init__(self, sdk) -> None:
        '''
        订单撮合meta类,实现基本新增订单,仓位管理,资金管理等
        :param sdk: 提供基本配置信息和行情推送功能
        '''
        self._sdk = sdk
        self._order_id = 0
        self._trade_id = 0
        self._orders = {}
        self._trade_orders = {}
        self._open_orders = {
            'sorted': True, # 未成交单是否排序
            'LONG': [],     # 多单未成交单
            'SHORT': []     # 空单未成交单
        }

        __tmpPosition = {
            'position': 0.0,        # 仓位大小
            'avg_cost': 0.0,        # 平均持仓成本
            'market_price': 0.0,    # 当前市价
            'margin': 0.0,          # 保证金
        }

        self._cur_position = {
            'LONG': copy.deepcopy(__tmpPosition),   # 当前多头持仓
            'SHORT': copy.deepcopy(__tmpPosition),  # 当前空头持仓
        }
        del __tmpPosition
        self._positions = []    # 所有持仓列表,外部调用
        self._coin = self._sdk._config['capitalCoin']       # 账户本位币种
        self._fee = self._sdk._config['fee']                # 账户交易手续费
        self._symbol = self._sdk._config['symbol']          # 当前标的名称
        self._cur_balance = {                               # 当前账户信息
            'baseCoin': self._coin,                         # 账户本位币种
            'free': self._sdk._config['initCapital'],       # 初始可用资金
            'frozen': 0.0,                                  # 未成交订单占用资金
            'total_margin': 0.0,                            # 成交订单保证金
            'unrealised_pnl': 0.0,                          # 未实现盈利
            'realized_pnl': 0.0,                            # 已实现盈利
            'fee': 0.0,                                     # 总手续费
            'total': self._sdk._config['initCapital']       # 账户总资金
        }
        self._initial_capital = self._sdk._config['initCapital']
        self._balance = []                         # 账户信息列表, 外部调用
        self._tsList = []
        self._marketList = []
        self._cur_trade_price = 0.0                # 当前市场价格
        
        self._last_data_timestamp = 0              # 当前行情推送时间戳

        self._position_mode = self._sdk._config['positionMode'] # 持仓模式,单向 single / 双项 cross
        self._precision = self._sdk._config.get('precision', 0) # 结果统计小数保留
        self._orders_actions = []

    def _get_curtime(self):
        '''
        返回当前行情推送时间戳
        '''
        return self._last_data_timestamp

    def _newOrder(self, px:float=None, qty:float=None, side:str='LONG', action:str='open', type:str='LIMIT', leverage:int=1):
        '''
        新增一个订单,记录新增相关信息
        Args:
            px: 订单价格
            qty: 订单数量
            side: 订单方向 Long Short
            action: 开仓:open 平仓:close
            type: 限价单 LIMIT 市价单 MARKET
            leverage: 杠杆率
        订单格式格式:
            symbol: 标的名称
            orderId: 订单编号
            side: 订单方向
            status: 当前订单状态
            px: 价格
            f_px: 平均成交价格
            qty: 数量
            f_qty: 成交数量
            u_qty: 未成交数量
            action: 订单动作
            fee: 手续费
            tpye: 订单类型
            c_time: 订单创建时间
            u_time: 订单更新时间
            leverage: 杠杆率
        Returns:
            下单操作结果 {'code': code, 'msg': code_info, 'data': order_info}
        '''
        # 无效仓位设定
        if not qty or qty <= 0.0:
            return {'code': Code.MINQTY_ERROR.value, 'msg': CODEINFO[Code.MINQTY_ERROR.value]}

        __type = type.upper()
        __side = side.upper()

        # 无效限价订单价格
        if px < 0.0 and __type != OrderType.MARKET.value:
            return {'code': Code.EXCEED_PX_ERROR.value, 'msg': CODEINFO[Code.EXCEED_PX_ERROR.value]}

        # type不包含在OrderType内
        if __type not in OrderType.__members__ or __side not in Side.__members__:
            return {'code': Code.PARAMS_ERROR, 'msg': CODEINFO[Code.PARAMS_ERROR.value]}

        if action == 'open':
            # 开仓量大于账户可用资金
            if px * qty > self._cur_balance['free']:
                return {'code': Code.FREE_BALANCE_ERROR.value, 'msg': CODEINFO[Code.FREE_BALANCE_ERROR.value]}
        else:
            # 平仓动作下, 方向-1代表平多头,检查多头仓位是否满足要求
            curPostion = self._cur_position['LONG'] if Side[side].value == 'SHORT' else self._cur_position['SHORT']
            # 当前方向仓位是否包含symbol
            if curPostion['position'] < qty:
                return {'code': Code.MAXVALUE_ERROR.value, 'msg': CODEINFO[Code.MAXVALUE_ERROR.value]}
        
        self._order_id += 1
        orderInfo = {
            'symbol': self._symbol,                 # 标的名称
            'order_id':self._order_id,              # 订单id
            'side': __side,                         # 订单方向
            'status': OrderStatus.OPEN.value,       # 订单状态为OPEN
            'px': px,                               # 价格
            'f_px': 0.0,                            # 平均成交价格
            'qty': qty,                             # 数量
            'f_qty': 0.0,                           # 成交数量
            'u_qty': qty,                           # 未成交数量
            'action': action,                       # 订单动作
            'fee': 0.0,                             # 手续费
            'type': __type,                         # 订单类型
            'c_time': self._last_data_timestamp,    # 创建订单时间戳
            'u_time': self._last_data_timestamp,    # 更新订单时间戳
            'leverage': leverage                    # 订单杠杆
        }

        # 添加未成交相应开仓方向订单列表
        self._orders[self._order_id] = orderInfo
        self._open_orders['sorted'] = False
        self._open_orders[side].append((orderInfo['order_id'], orderInfo['px']))

        # 更新账户冻结和可用资金
        if orderInfo['action'] == 'open':
            __curFrozen = self._format_data(px * qty / leverage)
            self._cur_balance['free'] = self._format_data(self._cur_balance['free'] - __curFrozen)
            self._cur_balance['frozen'] = self._format_data(self._cur_balance['frozen'] + __curFrozen)

        return {'code': Code.SUCCESS.value, 'msg': CODEINFO[Code.SUCCESS.value], 'data': orderInfo}

    def _format_data(self, data):
        '''
        返回保留小数点结果
        '''
        return data

    def _format_return(self, code=Code.SUCCESS.value, data=None):
        '''
        标准化返回结果
        '''
        return {
            'code': code,
            'msg': CODEINFO[code],
            'data': data
        }

    def _set_cur_trade_price(self, price:float):
        '''
        设置最新市价
        '''
        self._cur_trade_price = price

    def _union_update_position_balance(self, trade_order_id_pairs:list=[]):
        '''
        根据(订单号,成交单号)订单对列表更新持仓和账户信息
        :params trade_order_id_pairs: (order_id, trade_id)
        :return: trade_order_id_pairs
        '''

        # 更新持仓市价
        self._cur_position['LONG']['market_price'] = self._cur_position['SHORT']['market_price'] = self._cur_trade_price

        if len(trade_order_id_pairs):
            for order_id_pair in trade_order_id_pairs:
                __cur_trade_order = self._trade_orders[order_id_pair[1]]
                # 更新账户手续费相关结果
                self._cur_balance['fee'] = self._format_data(self._cur_balance['fee'] + __cur_trade_order['fee'])
                self._cur_balance['free'] = self._format_data(self._cur_balance['free'] - __cur_trade_order['fee'])
                self._cur_balance['total'] = self._format_data(self._cur_balance['total'] - __cur_trade_order['fee'])

                __target_order = self._orders[order_id_pair[0]]
                # 成交量增加/减少的保证金
                
                # 开仓情况
                if __cur_trade_order['action'] == 'open':
                    __add_margin = __cur_trade_order['f_amt'] / __target_order['leverage']
                    # 成交量扣减账户冻结量
                    __unfreeze = __target_order['px'] * __cur_trade_order['f_qty']
                    # 当前持仓方向与开仓方向一致
                    __cur_postion_title = 'LONG' if __cur_trade_order['side'] == 'LONG' else 'SHORT'
                    __alter_position_title = 'SHORT' if __cur_trade_order['side'] == 'LONG' else 'SHORT'
                    __cur_position = self._cur_position[__cur_postion_title]
                    __alter_position = self._cur_position[__alter_position_title]
                    __prev_open_amt = __cur_position['avg_cost'] * __cur_position['position']                               # 已成交量
                    __cur_total_qty = __cur_position['position'] + __cur_trade_order['f_qty']                               # 总成交量
                    
                    __cur_avg_cost = self._format_data((__prev_open_amt + __cur_trade_order['f_amt']) / __cur_total_qty)    # 当前平均持仓成本
                    __cur_position['avg_cost'] = __cur_avg_cost 
                    __cur_position['margin'] = self._format_data(__cur_position['margin'] + __add_margin)                   # 当前持仓方向增加保证金
                    __cur_position['position'] = __cur_total_qty    

                    self._cur_balance['frozen'] = self._format_data(self._cur_balance['frozen'] - __unfreeze)               # 当前冻结资金减少
                    self._cur_balance['free'] = self._format_data(self._cur_balance['free'] + __unfreeze - __add_margin)    # 账户可用资金增加解冻资金减去增加的保证金

                else:
                    # 平仓情况下,当前持仓与开仓方向相反
                    __cur_postion_title = 'SHORT' if __cur_trade_order['side'] == 'LONG' else 'LONG'
                    __alter_position_title = 'LONG' if __cur_trade_order['side'] == 'LONG' else 'SHORT'
                    __cur_position = self._cur_position[__cur_postion_title]
                    __alter_position = self._cur_position[__alter_position_title]

                    __add_margin = __cur_trade_order['f_qty'] * __cur_position['avg_cost']
                    __cur_position['position'] = self._format_data(__cur_position['position'] - __cur_trade_order['f_qty'])         # 当前仓位持仓减少
                    __cur_position['margin'] = self._format_data(__cur_position['margin'] - __add_margin)                           # 当前仓位保证金减少
                    __unfreeze = __cur_position['avg_cost'] * __cur_trade_order['f_qty']                                            # 前序平仓量
                    __flag = -1 if __cur_trade_order['side'] == 'LONG' else 1   
                    __new_realized_pnl = __flag * (__cur_trade_order['f_amt'] - __unfreeze)                                         # 计算当前已实现盈亏
                    self._cur_balance['realized_pnl'] = self._format_data(self._cur_balance['realized_pnl'] + __new_realized_pnl)   # 更新已实现盈亏
                    self._cur_balance['total'] = self._format_data(self._cur_balance['total'] + __new_realized_pnl)                 # 总资金增加已实现盈亏
                    self._cur_balance['free'] = self._format_data(self._cur_balance['free'] + __new_realized_pnl + __unfreeze)      # 可用资金增量为已实现盈亏和平仓量
                
                # 更新当前持仓
                self._cur_position[__cur_postion_title] = __cur_position
                self._cur_position[__alter_position_title] = __alter_position

        # 更新账户信息
        self._cur_balance['total_margin'] = self._format_data(self._cur_position['LONG']['margin'] + self._cur_position['SHORT']['margin'])     # 总保证金为多头持仓和空头持仓保证金总和
        __unrealized_pnl = (self._cur_trade_price - self._cur_position['LONG']['avg_cost']) * self._cur_position['LONG']['position'] - \
                    (self._cur_trade_price - self._cur_position['SHORT']['avg_cost']) * self._cur_position['SHORT']['position']                 # 计算当前持仓浮盈
        __delta_unrealized_pnl = __unrealized_pnl - self._cur_balance['unrealised_pnl']                                                         # 计算增量浮盈
        self._cur_balance['total'] = self._format_data(self._cur_balance['total'] + __delta_unrealized_pnl)                                     # 更新账户总资金
        self._cur_balance['free'] = self._format_data(self._cur_balance['free'] + __delta_unrealized_pnl)                                       # 更新账户可用资金
        self._cur_balance['unrealised_pnl'] = __unrealized_pnl                                                                                  # 更新账户浮盈
        
        assert round(self._cur_balance['total'], 4) == round(self._cur_balance['free'] + self._cur_balance['total_margin'] + self._cur_balance['frozen'], 4)
        assert round(self._initial_capital,4) == round(self._cur_balance['total'] + self._cur_balance['fee'] - self._cur_balance['unrealised_pnl'] - self._cur_balance['realized_pnl'], 4)
        return self._format_return(data=trade_order_id_pairs)
            
    def _open_orders_match(self):
        '''
        分别对单一方向未成交订单根据订单价格进行排序, 对排序后的订单与行情进行撮合
        '''
        if not self._open_orders['sorted']:
            if self._open_orders['LONG']:
                self._open_orders['LONG'].sort(key=lambda x:x[1], reverse=True)     # 多头仓位逆序
            if self._open_orders['SHORT']:
                self._open_orders['SHORT'].sort(key=lambda x:x[1])                  # 空头仓位顺序
            self._open_orders['sorted'] = True

        if self._open_orders['LONG']:
            __open_order_ids = [x[0] for x in self._open_orders['LONG']]
            self._one_side_open_orders_match(__open_order_ids)
        if self._open_orders['SHORT']:
            __open_order_ids = [x[0] for x in self._open_orders['SHORT']]
            self._one_side_open_orders_match(__open_order_ids)
            
        if not self._open_orders['LONG'] and not self._open_orders['SHORT']:
            self._union_update_position_balance([])

    def fetch_balance(self):
        '''
        获取当前账户信息
        '''
        __data = {
            'total': self._cur_balance['total'],
            'frozen': self._cur_balance['frozen'],
            'free': self._cur_balance['free'],
            'total_margin': self._cur_balance['total_margin'],
            'unrealised_pnl': self._cur_balance['unrealised_pnl'],
            'realized_pnl': self._cur_balance['realized_pnl'],
            'fee': self._cur_balance['fee']
        }
        return self._format_return(data=__data)

    def fetch_user_position(self, symbol=None):
        '''
        获取当前持仓
        '''
        __res_data = []
        for __side, v in self._cur_position.items():
            if v['position']:
                flag = 1 if __side == Side.LONG.name else -1
                unrealised_pnl = flag * (v['market_price'] - v['avg_cost']) * v['position']
                __res_data.append({
                    'symbol': self._symbol,
                    'position': v['position'],
                    'margin': v['margin'],
                    'avg_cost': v['avg_cost'],
                    'side': __side,
                    'unrealised_pnl': unrealised_pnl
                })
        return self._format_return(data=__res_data)

    def cancel_order(self, order_id):
        '''
        取消指定订单
        :param order_id: 订单id
        :return code msg order_id
        '''
        __cur_order = self._orders[order_id]
        __cur_open_order_ids = [x[0] for x in self._open_orders[__cur_order['side']]]                   # 获取同向未成交订单
        if order_id in __cur_open_order_ids:
            self._orders[order_id]['u_time'] = self._get_curtime()                                      # 更新订单时间
            self._orders[order_id]['status'] = OrderStatus.CANCELED.value                               # 更新订单状态
            self._open_orders[__cur_order['side']].remove((order_id, __cur_order['px']))                # 移除列表
        
            # 更新冻结资金
            __frozen = __cur_order['px'] * __cur_order['u_qty']
            self._cur_balance['fronzen'] = self._format_data(self._cur_balance['fronzen'] - __frozen)
            self._cur_balance['free'] = self._format_data(self._cur_balance['free'] + __frozen)
            return self._format_return(data={'order_id':order_id})
        else:
            return self._format_return(code=Code.UNEXIST_ERROR, data={'order_id':order_id})

    def cancel_all_order(self)->dict:
        '''
        取消所有为成交订单
        :return code msg order_ids
        '''
        __total_frozen = 0.0
        __cur_time = self._get_curtime()
        __ids = []
        def cancel_one_direction_open_orders(orders, total_frozen):
            '''
            单一持仓方向取消订单,统计解冻资金
            :param orders: 单一方向未成交订单
            :param total_frozen: 统计解冻资金
            '''
            for item in orders:
                __cur_order_id = item[0]
                __ids.append(__cur_order_id)
                self._orders[__cur_order_id]['status'] = OrderStatus.CANCELED.value                             # 更新订单状态
                self._orders[__cur_order_id]['u_time'] = __cur_time                                             # 更新订单时间
                if self._orders[__cur_order_id]['action'] == 'open':                                            # 开仓状态增加解冻资金
                    total_frozen += self._orders[__cur_order_id]['px'] * self._orders[__cur_order_id]['u_qty']
            return total_frozen

        __total_frozen = cancel_one_direction_open_orders(self._open_orders['LONG'], __total_frozen)
        __total_frozen = cancel_one_direction_open_orders(self._open_orders['SHORT'], __total_frozen)

        self._open_orders['LONG'] = []
        self._open_orders['SHORT'] = []
        self._cur_balance['frozen'] = self._format_data(self._cur_balance['frozen'] - __total_frozen)           # 更新账户冻结资金
        self._cur_balance['free'] = self._format_data(self._cur_balance['free'] + __total_frozen)               # 更新账户可用资金

        return self._format_return(data={'order_ids': __ids})

    def fetch_open_orders(self)->dict:
        '''
        获取所有未成交订单
        :return code msg open_orders
        '''
        __open_ids = [x[0] for x in (self._open_orders['LONG'] + self._open_orders['SHORT'])]
        __res = [self._orders[__id] for __id in __open_ids]
        return self._format_return(data=__res)

    def fetch_order(self, order_id)->dict:
        '''
        获取指定订单当前信息
        :param order_id: 
        :return code msg order_info
        '''
        return self._format_return(data=self._orders[order_id])
    
    def create_order(self, symbol, px=0.0, qty=0.0, side='LONG', type='LIMIT', leverage=1):
        '''
        创建新订单,子类实现
        '''
        raise NotImplemented

    def match(self, order, timestamp)->dict:
        '''
        订单与推送行情进行匹配,分为tick和depth,子类实现
        '''
        raise NotImplemented

    def _one_side_open_orders_match(self, open_ids)->list:
        '''
        单一方向未成交订单匹配,子类实现
        '''
        raise NotImplemented
    
    def iteration(self):
        '''
        行情推送处理,子类实现
        '''
        raise NotImplemented

    def summary(self):
        current = self._cur_trade_price
        content = f"Daily Report|current:{current} balance:{self._balance[-1]:0.2f} netPosition:{self._positions[-1]:0.4f}"
        self._sdk._log.write(content)
    
    def close(self):
        """每个用户perCycle之后的动作
        """        
        self._tsList.append(self._last_data_timestamp)
        self._balance.append(self._cur_balance['total'])
        self._positions.append(
            self._cur_position['LONG']['position'] - self._cur_position['SHORT']['position']
        )
        self._marketList.append(self._cur_trade_price)

    def _tradesLog(self, order):
        action = order['action']
        side = order['side']
        if action=='close':
            side = 'LONG' if order['side']=='SHORT' else 'SHORT'
        content = f"{self._sdk.getTime()} Deal Match|{self._symbol} {action.upper()}_{side} {order['f_px']} {order['f_qty']}"
        self._sdk._log.write(content)
    
    def evaluate(self):
        self._balance = self._balance[::120]
        netAsset = self._balance[-1]/self._balance[0]
        annualReturn = (netAsset-1)/(len(self._sdk._playback.dateList)-1)*365
        netAssetDF = pd.DataFrame(self._balance)
        self.drawdownSeries = netAssetDF/netAssetDF.cummax()
        maxDrawdown = self.drawdownSeries.min().values[0]-1

        content = f"\n策略总结\n"
        content += f"期末净值:{netAsset:0.3f} 年化收益:{annualReturn*100:0.2f}% 最大回撤:{maxDrawdown*100:0.2f}%\n"
        self._conclusion = content
        self.trade_orders_statistic()

        # draw
        self.draw()
    
    def draw(self):
        self._sdk._log.write('等待画图.....')
        from plotly.subplots import make_subplots
        import plotly.graph_objects as go 
        import time
        start = time.time()

        self._balance = self._balance
        self._marketList = self._marketList[::120]
        self._positions = self._positions[::120]
        self.drawdownSeries = self.drawdownSeries.values.flatten()
        self._tsList = self._tsList
        ts = [self._sdk.getTime(i, strFormat='%Y-%m-%d %H:%M:%S') for i in self._tsList[::120]]

        fig = make_subplots(
            rows=3, 
            cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.01, 
            row_heights=[0.4,0.4,0.2], 
            specs=[[{"secondary_y": False}], [{"secondary_y": False}], [{"secondary_y": True}]])

        fig.add_trace(go.Scatter(x=ts, y=self._positions, name='position', line_color='rgba(170, 170, 170, 1)', opacity=0.8), row=3, col=1)

        fig.add_trace(go.Scatter(x=ts, y=self._balance/self._balance[0], name='strategy', line_color='rgba(82, 165, 248, 1)'), row=1, col=1)
        fig.add_trace(go.Scatter(x=ts, y=self._marketList/self._marketList[0], name='market', line_color='rgba(255, 190, 66, 1)'), row=1, col=1)
        fig.add_trace(go.Scatter(x=ts, y=self.drawdownSeries, name='drawback', line_color='rgba(233, 97, 64, 1)'), row=1, col=1)

        fig.add_trace(go.Scatter(x=ts, y=self._marketList, name='price', line_color='rgba(255, 190, 66, 1)', opacity=0.8), row=2, col=1)

        profits = []
        profitsIdx = []
        losses = []
        lossesIdx = []
        ol = []
        olIdx = []
        cl = []
        clIdx = []
        os = []
        osIdx = []
        cs = []
        csIdx = []
        for order in self._orders_actions:
            t, side, offset, pl = order
            index = self._tsList.index(t)//120
            if pl>0:
                profitsIdx.append(ts[index])
                profits.append(pl)
            elif pl<0:
                lossesIdx.append(ts[index])
                losses.append(pl)
            if side==offset==1:
                olIdx.append(ts[index])
                ol.append(self._marketList[index])
            elif side==offset==-1:
                clIdx.append(ts[index])
                cl.append(self._marketList[index]*1.002)
            elif side==1 and offset==-1:
                csIdx.append(ts[index])
                cs.append(self._marketList[index]*1.002)
            elif side==-1 and offset==1:
                osIdx.append(ts[index])
                os.append(self._marketList[index])

        long_color = 'rgba(233, 97, 64, 1)'
        short_color = 'rgba(101, 218, 120, 1)'
        fig.add_trace(go.Scatter(x=olIdx, y=ol, mode='markers', marker_symbol='circle', marker_color=long_color, name='open long', marker_size=10), row=2, col=1)
        fig.add_trace(go.Scatter(x=clIdx, y=cl, mode='markers', marker_symbol='x', marker_color=short_color, name='close long', marker_size=10), row=2, col=1)
        fig.add_trace(go.Scatter(x=osIdx, y=os, mode='markers', marker_symbol='circle', marker_color=short_color, name='open short', marker_size=10), row=2, col=1)
        fig.add_trace(go.Scatter(x=csIdx, y=cs, mode='markers', marker_symbol='x', marker_color=long_color, name='close short', marker_size=10), row=2, col=1)
        fig.add_trace(go.Scatter(x=profitsIdx, y=profits, mode='markers', marker_color=long_color, name='profit', marker_size=10), row=3, col=1, secondary_y=True)
        fig.add_trace(go.Scatter(x=lossesIdx, y=losses, mode='markers', marker_color=short_color, name='loss', marker_size=10), row=3, col=1, secondary_y=True)

        fig.update_layout(plot_bgcolor='rgba(0, 0, 0, 0)')
        fig.update_xaxes(showline=True, linewidth=2, linecolor='rgba(240, 240, 240, 0.8)', gridcolor='rgba(240, 240, 240, 0.8)')
        fig.update_yaxes(showline=True, linewidth=2, linecolor='rgba(240, 240, 240, 0.8)', gridcolor='rgba(240, 240, 240, 0.8)')

        self._sdk._log.write(f'画图完毕! 耗时:{(time.time()-start):0.2f}s')
        fig.show()

    def trade_orders_statistic(self):
        __trade_order_list = [order for _, order in self._trade_orders.items()]
        __trade_order_list.sort(key=itemgetter('c_time'))
        __long_position = []
        __short_position = []
        __cur_long_position = {
            'c_time': 0,
            'avg_cost': 0.0,
            'qty': 0.0,
            'pnl': 0.0,
            'amt': 0.0,
            'fee': 0.0,
            'side': Side.LONG.name,
            'e_time': 0
        }
        __cur_short_position = {
            'c_time': 0,
            'avg_cost': 0.0,
            'qty': 0.0,
            'pnl': 0.0,
            'amt': 0.0,
            'fee': 0.0,
            'side': Side.SHORT.name,
            'e_time': 0
        }

        for __trade in __trade_order_list:
            __position_flag = [__trade['c_time']]
            __position_flag.append(1) if __trade['side'] == Side.LONG.name else __position_flag.append(-1)
            if __trade['action'] == 'open':
                __cur_position = __cur_long_position if __trade['side'] == Side.LONG.name else __cur_short_position
                if not __cur_position['c_time']:
                    __cur_position['c_time'] = __trade['c_time']
                    __cur_position['side'] = __trade['side']
                __cur_position['amt'] += __trade['f_amt']
                __cur_position['qty'] += __trade['f_qty']
                __cur_position['avg_cost'] = __cur_position['amt'] / __cur_position['qty']
                __cur_position['fee'] += __trade['fee']
                __position_flag += [1, 0.0]
            else:
                __cur_position = __cur_long_position if __trade['side'] == Side.SHORT.name else __cur_short_position
                __flag = 1 if __trade['side'] == Side.SHORT.name else -1
                __offset_amt = __trade['f_qty'] * __cur_position['avg_cost']
                __pnl = __flag * (__trade['f_amt'] - __offset_amt)
                __cur_position['pnl'] += __pnl
                __cur_position['amt'] -= __offset_amt
                __cur_position['qty'] -= __trade['f_qty']
                __cur_position['fee'] += __trade['fee']
                __position_flag += [-1, __pnl]
                if __cur_position['amt'] == 0.0:
                    __cur_position['e_time'] = __trade['c_time']
                    if __trade['side'] == Side.SHORT.name:
                        __long_position.append(copy.deepcopy(__cur_position))
                    else:
                        __short_position.append(copy.deepcopy(__cur_position))
                    __cur_position['c_time'] = 0
                    __cur_position['avg_cost'] = 0.0
                    __cur_position['qty'] = 0.0
                    __cur_position['pnl'] = 0.0
                    __cur_position['amt'] = 0.0
                    __cur_position['fee'] = 0.0
                    __cur_position['e_time'] = 0.0

            self._orders_actions.append(__position_flag)

        trade_nums = {
            'LONG': len([x for x in __trade_order_list if x['side'] == Side.LONG.name]),
            'SHORT': len([x for x in __trade_order_list if x['side'] == Side.SHORT.name]),
            'TOTAL': len(__trade_order_list)
        }

        open_close_nums = {
            'LONG': len(__long_position),
            'SHORT': len(__short_position),
            'TOTAL': len(__long_position) + len(__short_position)
        }

        def __cal_win_ratio_pl_ratio(positions):
            if len(positions):
                pnls = [x['pnl'] for x in positions]
                win_count = len([i for i in pnls if i > 0])
                win_value = sum([i for i in pnls if i >= 0 ]) / len([i for i in pnls if i >= 0 ]) if len([i for i in pnls if i >= 0 ]) else inf
                loss_value = sum([i for i in pnls if i < 0]) / len([i for i in pnls if i < 0 ]) if len([i for i in pnls if i < 0 ]) else inf
                win_ratio = win_count / len(positions)
                pl_ratio = win_value / loss_value if loss_value !=0 else inf
                return win_ratio, abs(pl_ratio)
            return 0.0, 0.0

        __long_win_ratio, __long_pl_ratio = __cal_win_ratio_pl_ratio(__long_position)
        __short_win_ratio, __short_pl_ratio = __cal_win_ratio_pl_ratio(__short_position)
        __total_win_ratio, __total_pl_ratio = __cal_win_ratio_pl_ratio(__long_position + __short_position)

        win_ratio =  {
            'LONG': __long_win_ratio,
            'SHORT': __short_win_ratio,
            'TOTAL': __total_win_ratio
        }

        pnl_ratio = {
            'LONG': __long_pl_ratio,
            'SHORT': __short_pl_ratio,
            'TOTAL': __total_pl_ratio
        }

        mean_holding_time = {
            'LONG': mean([x['e_time'] - x['c_time'] for x in __long_position])/60000 if __long_position else 0.0,
            'SHORT': mean([x['e_time'] - x['c_time'] for x in __short_position])/60000 if __short_position else 0.0,
            'TOTAL': mean([x['e_time'] - x['c_time'] for x in __long_position + __short_position])/60000 if __long_position + __short_position else 0.0
        }
        # print({
        #     'trade_nums': trade_nums,
        #     'open_close_nums': open_close_nums,
        #     'win_ratio': win_ratio,
        #     'pnl_ratio': pnl_ratio,
        #     'mean_holding_time': mean_holding_time
        # })
        self._conclusion += f"交易次数 总:{trade_nums['TOTAL']} 多:{trade_nums['LONG']} 空:{trade_nums['SHORT']}\n"
        self._conclusion += f"开平回合 总:{open_close_nums['TOTAL']} 多:{open_close_nums['LONG']} 空:{open_close_nums['SHORT']}\n"
        self._conclusion += f"胜率 总:{win_ratio['TOTAL']*100:0.2f}% 多:{win_ratio['LONG']*100:0.2f}% 空:{win_ratio['SHORT']*100:0.2f}%\n"
        self._conclusion += f"盈亏比 总:{pnl_ratio['TOTAL']:.1f} 多:{pnl_ratio['LONG']:.1f} 空:{pnl_ratio['SHORT']:.1f}\n"
        self._conclusion += f"平均持仓时间(mins) 总:{mean_holding_time['TOTAL']:.1f} 多:{mean_holding_time['LONG']:.1f} 空:{mean_holding_time['SHORT']:.1f}"
        self._sdk._log.write(self._conclusion)
        # return {
        #     'trade_nums': trade_nums,
        #     'open_close_nums': open_close_nums,
        #     'win_ratio': win_ratio,
        #     'pnl_ratio': pnl_ratio,
        #     'mean_holding_time': mean_holding_time
        # }
    

