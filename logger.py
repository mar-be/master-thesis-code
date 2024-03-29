import logging
import sys
from typing import Dict

class StreamToLogger(object):
    """
    Fake file-like stream object that redirects writes to a logger instance.
    """
    def __init__(self, logger, log_level=logging.INFO):
        self.logger = logger
        self.log_level = log_level
        self.linebuf = ''

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.log_level, line.rstrip())

    def flush(self):
        pass

log_level = "DEBUG"

def get_logger(name:str) -> logging.Logger:
    log = logging.getLogger(name)
    log.setLevel(log_level)
    formatter = logging.Formatter(fmt="%(asctime)s %(levelname)-8s %(name)s: %(message)s", 
                            datefmt="%Y-%m-%d - %H:%M:%S")
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    log.addHandler(ch)
    # sl = StreamToLogger(log)
    # sys.stdout = sl

    return log

def set_log_level_from_config(config:Dict):
    global log_level 
    log_level = config["logger"]["level"]