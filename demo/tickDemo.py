from mexcBT.backTest import sdk
from collections import deque
import pandas as pd

class Strategy(sdk):


    def prepare(self):
        """策略开始前的准备  config里的所有key都会赋值到self
        """        
        self.qty = 0.1  # 满仓下单量
        self.length = 7200 # 队列长度
        self.net = deque(maxlen=self.length)  # 定长队列
        self.longFlag = False  # 是否持多仓
        self.shortFlag = False  # 是否持空仓
        self.totalNet = None  # 是否记录了总net
        self.totalNetList = []  # 策略结束后复盘用
        self.percent = 0.53  # 多空数量比
        self.value = round(self.length*self.percent-self.length*(1-self.percent), 0)  # 多空flag差值
        print(f"value: {self.value}")

    def perCycle(self):
        """按深度回放
        策略主逻辑
        """      
        depth = self.fetch_order_book(self.symbol)  # 拿取当前深度
        bidVol = sum(depth[0, :5, 1])  # 算5档买量和
        askVol = sum(depth[1, :5, 1])  # 算5档卖量和
        flag = 1 if bidVol>askVol else -1  # 记压力flag

        ''' 自定义算法模块 '''
        if self.totalNet is not None:
            self.totalNet += (flag-self.net[0])
            self.totalNetList.append(self.totalNet)

        self.net.append(flag)

        if len(self.net)<self.length:
            return
        if len(self.net)==self.length and self.totalNet is None:
            self.totalNet = sum(self.net)
        ''' 自定义算法模块 '''

        if self.totalNet>=self.value and not self.longFlag:
            pos = self.fetch_user_position()['data']  # 获取仓位

            if len(pos)!=0:
                short = {'position': i['position'] for i in pos if i['side']=='SHORT'}.get('position', 0)
            else:
                short = 0
            if short != 0:
                # 若有空仓先平仓
                self.create_order(self.symbol, 0, qty=short, side='CLOSE_SHORT', type='MARKET')  # 下市价单
            self.create_order(self.symbol, 0, qty=self.qty, side='LONG', type='MARKET')  # 下市价单
            
            # 避免重复开仓
            self.longFlag = True
            self.shortFlag = False

        elif self.totalNet<=-self.value and not self.shortFlag:
            pos = self.fetch_user_position()['data']  # 获取仓位
            if len(pos)!=0:
                long = {'position': i['position'] for i in pos if i['side']=='LONG'}.get('position', 0)
            else:
                long = 0
            if long != 0:
                self.create_order(self.symbol, 0, qty=long, side='CLOSE_LONG', type='MARKET')  # 下市价单
            self.create_order(self.symbol, 0, qty=self.qty, side='SHORT', type='MARKET')  # 下市价单
            
            # 避免重复开仓
            self.shortFlag = True
            self.longFlag = False

    def review(self):
        """策略结束后 用户自定义的复盘
        """         
        data = pd.DataFrame(self.totalNetList)
        print(data.describe())  # 查看flag序列总结
        # print(len(self._match._balance))
        # print(len(self._match._positions))
        
        # print(self._match._balance)


def main():
    config = {
        'h5Path': '/Users/admin/python3/ReCrypto/dataBase/h5/binanceUsdtSwap/btc-usdt',  # 用户h5文件夹路径
        'strategy': 'tickDemo',
        'startDate': 20220422,
        'endDate': 20220427,
        'symbol': 'btc/usdt',
        'exchange': 'binanceUsdtSwap',
        'cycle': 'tick', #tick or 1min
        
        'initCapital': 5000,
        'capitalCoin': 'usdt',
        'fee': 0.0005,  
        'positionMode': 'cross',  # 双向持仓
    }
    task = Strategy(config)
    task.run()


if __name__ == '__main__':
    main()