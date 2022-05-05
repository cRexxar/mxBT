from .. import tools
import os
import h5py as h5


class Core():

    def __init__(self, rootPath=None):
        rootPath = os.path.join(os.path.split(os.path.realpath(__file__))[0], 'h5') if rootPath is None else rootPath
        # self.log = tools.Log(os.path.join(rootPath, 'dataBase.log'))
        # self.paths = {
        #     # 'csv': os.path.join(rootPath, 'csv/'),
        #     'h5': os.path.join(rootPath, 'h5/'),
        #     # 'factor': os.path.join(rootPath, 'factor/'),
        # }
        # self.headDic = {
        #     'tick': ['price', 'vol', 'side'],
        #     'depth': ['bids', 'asks'],
        #     'kline1m': ['high', 'open', 'low', 'close', 'volume', 'amount', 'bidVolume', 'bidAmount'],
        # }
        tools.makeFolders([rootPath])
        self.rootPath = rootPath

    def getTick(self, symbol='btc/usdt', date=None, exc='binanceUsdtSwap',):
        with h5.File(
            os.path.join(self.rootPath, f"{date}_{exc}_{symbol.replace('/', '-')}_tick.h5"), 'r'
        ) as f:
            dic = {k: v[:] if k!='head' else [i.decode() for i in v[:]] for k, v in f.items()}
        return dic

    def getDepth(self, symbol='btc/usdt', date=None, exc='binanceUsdtSwap',):
        with h5.File(
            os.path.join(self.rootPath, f"{date}_{exc}_{symbol.replace('/', '-')}_depth.h5"), 'r'
        ) as f:
            dic = {k: v[:] if k!='head' else [i.decode() for i in v[:]] for k, v in f.items()}
        return dic

    def getKline1m(self, symbol='btc/usdt', date=None, exc='binanceUsdtSwap',):
        with h5.File(
            os.path.join(self.rootPath, f"{date}_{exc}_{symbol.replace('/', '-')}_kline1m.h5"), 'r'
        ) as f:
            dic = {k: v[:] if k!='head' else [i.decode() for i in v[:]] for k, v in f.items()}
        return dic        

SDK = Core()

        



        