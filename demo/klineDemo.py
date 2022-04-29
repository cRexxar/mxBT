from mexcBT.backTest import sdk

class Strategy(sdk):


    def prepare(self):
        """策略开始前的准备  config里的所有key都会赋值到self
        """        
        self.flag = 0
        self.qty = 0.1
        self.longFlag = False
        self.shortFlag = False
        self.size = 500
        pass

    def perCycle(self):
        """按深度回放
        策略主逻辑
        """      
        kline = self.fetch_ohlcv(self.symbol, '1m', size=self.size)
        if len(kline)<self.size:
            return
        else:
            if not self.longFlag and kline[-1][4] > max(i[1] for i in kline[:-1]):
                print(kline[-1][4], max(i[1] for i in kline[:-1]))
                pos = self.fetch_user_position()['data']  # 获取仓位

                if len(pos)!=0:
                    short = {'position': i['position'] for i in pos if i['side']=='SHORT'}.get('position', 0)
                else:
                    short = 0
                if short != 0:
                    # 若有空仓先平仓
                    res = self.create_order(self.symbol, 0, qty=short, side='CLOSE_SHORT', type='MARKET')  # 下市价单
                self.create_order(self.symbol, 0, qty=self.qty, side='LONG', type='MARKET')  # 下市价单
                self.longFlag = True
                self.shortFlag = False
            
            elif not self.shortFlag and kline[-1][4] < min(i[3] for i in kline[:-1]):
                print(kline[-1][4], max(i[3] for i in kline[:-1]))
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
        pass



def main():
    config = {
        'h5Path': '/Users/admin/python3/ReCrypto/dataBase',  # 用户h5文件夹路径
        'strategy': 'klineDemo',
        'startDate': 20220422,
        'endDate': 20220428,
        'symbol': 'btc/usdt',
        'exchange': 'binanceUsdtSwap',
        'cycle': '1min', #tick or 1min
        'klineInterval': ['3m', '1h', '1d', '1w', '2d'],  # 提前声明需要用到的kline周期
        
        'initCapital': 5000,
        'capitalCoin': 'usdt',
        'fee': 0.0005,  
        'positionMode': 'cross',  # 双向持仓
        # 'volumeThreshold': 0.5,  分钟线成交量撮合阈值
    }
    task = Strategy(config)
    task.run()


if __name__ == '__main__':
    main()