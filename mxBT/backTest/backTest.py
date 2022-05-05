from . import tools
import time
from .playback import Playback
from .match.tickMatch import TickMatch
from .match.klineMatch import KlineMatch


class Process():

    def __init__(self, config):
        self._config = config
        self._playback = Playback(sdk=self)
        self._match = TickMatch(sdk=self) if config['cycle']=='tick' else KlineMatch(sdk=self)
        
        [setattr(self, k, v) for k, v in self._config.items()]

        # rootPath = os.path.join(os.path.split(os.path.realpath(__file__))[0], 'backTestLogs')
        # tools.makeFolders([rootPath])
        # self._log = tools.Log(os.path.join(rootPath, f"{config.get('strategy', 'unknown')}.log"))
        self._log = tools.Log(f"{config.get('strategy', 'unknown')}_backTest.log")

    def _perCycle(self):
        """每个bar实际运行的函数(带撮合)
        """        
        self._match.iteration()
        self.perCycle()
        self._match.close()

    def run(self):
        self.prepare()
        for date in self._playback.dateList:  # 按粒度拆分数据
            _start = time.time()*1000
            self._log.write(f"===开始回测{date}===")
            self._playback.th_loadData()  # 读取数据
            self._playback.iterFunc()  # 回放函数
            self._match.summary()  # 撮合每日扎帐
            self._log.write(f"===结束回测{date} 耗时:{(time.time()*1000-_start):0.2f}ms===")

        self.review()
        self._match.evaluate()  # 分析
    
    def getTime(self, ts=None, strFormat='%Y-%m-%d %H:%M:%S'):
        if ts is None:
            return tools.reTimestamp(self._playback.ts/1000, strFormat=strFormat)
        else:
            return tools.reTimestamp(ts/1000, strFormat=strFormat)
        
    def getTs(self):
        return self._playback.ts

    def getTick(self):
        return self._playback.ticks
    
    def getKline(self):
        return self._playback.klines[-1]
    
    def getDepth(self):
        return self._playback.depth

    def create_order(self, symbol, px, qty, side='LONG', type='LIMIT', leverage=1):
            
        return self._match.create_order(symbol, px, qty, side, type, leverage)

    def fetch_balance(self):
        return self._match.fetch_balance()

    def fetch_user_position(self, symbol=None):
        return self._match.fetch_user_position(symbol=symbol)

    def cancel_order(self, order_id):
        return self._match.cancel_order(order_id)

    def cancel_all_order(self):
        return self._match.cancel_all_order()

    def fetch_open_orders(self):
        return self._match.fetch_open_orders()

    def fetch_order(self, order_id):
        return self._match.fetch_order(order_id)

    
        
    def getBalanceList(self):
        return self._match.getBalanceList()
    
    # def getKline(self):
    #     return self._playback.klines
    
    def fetch_order_book(self, symbol, size=10):
        # result = {
        #     'code': 100000,
        #     'msg': '',
        #     'data': {
        #         'bids': self._playback.depth[0].tolist(),
        #         'asks': self._playback.depth[1].tolist()
        #     },
        #     'timestamp': self._playback.ts
        # }
        # return result
        return self._playback.depth[:, :size, :]
    
    def fetch_trades(self, symbol, size=100):
        # result = {
        #     'code': 100000,
        #     'msg': '',
        #     'data': list(self._playback.ticks)[-size:][::-1],
        # }
        # return result
        return list(self._playback.ticks)[-size:]
    
    def fetch_ohlcv(self, symbol, interval='1m', size=1):
        if interval == '1m':
            return list(self._playback.klines)[-size:]
        else:
            try:
                cycle = self._playback.klineDict[interval[-1]]*int(interval[:-1])
                return list(self._playback.klinesBase[cycle])[-size:]
            except:
                raise Exception(f'klineInterval声明里未找到{interval} 检查config配置!!')
    

sdk = Process

        


