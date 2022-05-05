import threading
import pandas as pd
from collections import deque
from .dataBase import Core


class Playback():

    def __init__(self, sdk):
        self.sdk = sdk
        self.db = Core(sdk._config.get('h5Path', None))
        self.symbol = sdk._config['symbol']
        self.exc = sdk._config['exchange']
        self.cycle = sdk._config['cycle']
        self.klineInterval = sdk._config.get('klineInterval', [])
        self.dataOffset = 0
        self.dateList = [
            str(d)[:10].replace('-', '') for d in pd.date_range(str(sdk._config['startDate']), str(sdk._config['endDate']))
        ]
        self.klineDict = {
            'm': 1,
            'h': 60,
            'd': 1440,
            'w': 10080,
        }
        self.ticks = deque(maxlen=100)  # tick队列
        self.klines = deque(maxlen=525600)
        self.checkKlineInterval()  # 检查分钟线周期声明

    def mergeKline(self, klineTs, klineData):
        for k, v in self.klinesBase.items():
            if len(v) == 0:
                v.append([klineTs, *klineData, 0])
                continue
            
            if self.klineOffset<k or self.klineOffset%k != 1:
                v[-1][0] = klineTs
                v[-1][1] = max(v[-1][1], klineData[0])
                v[-1][3] = min(v[-1][3], klineData[2])
                v[-1][4] = klineData[3]
                v[-1][5] = v[-1][5]+ klineData[4]
                v[-1][6] = v[-1][6]+ klineData[5]
                v[-1][7] = v[-1][7]+ klineData[6]
                v[-1][8] = v[-1][8]+ klineData[7]

                if self.klineOffset%k == 0:
                    v[-1][-1] = 1

            elif self.klineOffset%k == 1:
                v.append([klineTs, *klineData, 0])

    def _loadData(self):
        try:
            date = self.dateList[self.dataOffset]
        except IndexError:
            return
        
        if self.cycle=='tick':
            self._pre_tick = self.db.getTick(date=date, symbol=self.symbol, exc=self.exc)
            self._pre_depth = self.db.getDepth(date=date, symbol=self.symbol, exc=self.exc)
            self._pre_kline = self.db.getKline1m(date=date, symbol=self.symbol, exc=self.exc)
        elif self.cycle=='1min':
            self._pre_kline = self.db.getKline1m(date=date, symbol=self.symbol, exc=self.exc)

        self.dataOffset += 1
    
    def th_loadData(self):
        """线程预读第二天数据
        """        
        if 'preLoadProcess' in dir(self):
            self.preLoadProcess.join()
        else:
            self._loadData()

        if self.cycle=='tick':
            setattr(self, '_current_tick', self._pre_tick)
            setattr(self, '_current_depth', self._pre_depth)
            setattr(self, '_current_kline', self._pre_kline)
            pass
        elif self.cycle=='1min':
            setattr(self, '_current_kline', self._pre_kline)
            pass

        self.preLoadProcess = threading.Thread(target=self._loadData, args=())
        self.preLoadProcess.start()

    def checkKlineInterval(self):
        self.klinesBase = {}
        for interval in self.klineInterval:
            if interval!='1m':
                multiplier = self.klineDict[interval[-1]]
                cycle = multiplier*int(interval[:-1])
                self.klinesBase[cycle] = deque(maxlen=52600)
        self.klineOffset = 0

    def iterFunc(self):

        if self.cycle=='tick':
            tick = self._current_tick
            depth = self._current_depth
            kline = self._current_kline
            tickPos = 0
            klinePos = 0
            # self.klines = []
            # self.ticks = deque(maxlen=100)
            # self.ticks = []

            for depthIndex, depthTs in enumerate(depth['timestamp']):
                if depthIndex==0:
                    preDepthTs = depthTs
                    continue

                self.depth = depth['data'][depthIndex]
                self.ts = depthTs
                # self.ticks = []

                for tickIndex, tickTs in enumerate(tick['timestamp'][tickPos:]):
                    if tickTs<=depthTs:
                        # idx = tickPos+tickIndex
                        self.ticks.append([tickTs, *tick['data'][tickPos+tickIndex]])

                        # data = tick['data'][idx]
                        # self.ticks.append({
                        #     'px': data[0],
                        #     'qty': data[1],
                        #     'side': 'LONG',
                        #     'timestamp': tick['timestamp'][idx],
                        # })
                        continue

                    elif tickTs>depthTs:
                        # idx = slice(tickPos+tickIndex-100, tickPos+tickIndex) 
                        # self.ticks = np.hstack([tick['timestamp'][idx].reshape(-1, 1), tick['data'][idx]])
                        # self.ticks = tick['data'][idx]
                        tickPos += tickIndex
                        break
                
                for klineIndex, klineTs in enumerate(kline['timestamp'][klinePos:]):
                    if klineTs>self.ts:
                        klinePos += klineIndex
                        break
                    else:   
                        self.klines.append([klineTs, *kline['data'][klinePos+klineIndex], 1])
                        self.mergeKline(klineTs, kline['data'][klinePos+klineIndex])
                        continue
                
                # preDepthTs = depthTs
                self.sdk._perCycle()
        
        elif self.cycle == '1min':
            kline = self._current_kline
            for klineIndex, klineTs in enumerate(kline['timestamp']):
                self.klineOffset += 1
                self.ts = klineTs
                self.klines.append([klineTs, *kline['data'][klineIndex], 1])
                # print(self.klines)

                self.mergeKline(klineTs, kline['data'][klineIndex])


                self.sdk._perCycle()