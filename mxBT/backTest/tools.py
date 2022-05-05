import logging
import logging.handlers
import inspect
import datetime
import pytz
import os


def timestamp(tz='Asia/Singapore', strFormat='%Y-%m-%d %H:%M:%S'):
    """generate tiemstamp in particular timezone

    Args:
        tz (str, optional): time zone. Defaults to 'Asia/Singapore'.
        strFormat (str, optional): timestamp format. Defaults to '%Y-%m-%d %H:%M:%S'.
    """    
    tz = pytz.timezone(tz)
    now = datetime.datetime.now(tz).strftime(strFormat)
    return now

def reTimestamp(ts, tz='Asia/Singapore', strFormat='%Y-%m-%d %H:%M:%S'):
    utcDate = datetime.datetime.utcfromtimestamp(ts)
    utcTime = pytz.utc.localize(utcDate)
    now = utcTime.astimezone(pytz.timezone(tz)).strftime(strFormat)
    return now


def makeFolders(folders):
    for folder in folders:
        if not os.path.exists(folder):
            os.makedirs(folder)

class Log():

    def __init__(self, fileName, backupSize=50, backupNum=3):
        """logging

        Args:
            fileName (str): name of log(endswith .log)
            backupSize (int, optional): backup file size(MB). Defaults to 50.
            backupNum (int, optional): backup file number. Defaults to 3.
        """        
        self.logger = logging.getLogger(fileName)
        handler = logging.handlers.RotatingFileHandler(
            filename=fileName,
            maxBytes=1024*1024*backupSize,
            backupCount=backupNum,
            encoding='utf-8',
            delay=False,
        )
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        handler.setLevel(logging.CRITICAL)
        self.logger.addHandler(handler)
        self.fileName = fileName
        # self.write('==========Init Log==========')
    
    def write(self, content='', funcName=None):
        """write in log

        Args:
            content (str, optional): content. Defaults to ''.
            funcName (_type_, optional): content from which function. Defaults to None.
        """        
        funcName = inspect.stack()[1][3] if funcName is None else funcName
        ts = timestamp(strFormat='%Y-%m-%d %H:%M:%S.%f')
        content = f"=={ts}=={funcName} | {content}"
        self.logger.critical(content)
        # print(f"{self.fileName}: {content}")
        print(content)