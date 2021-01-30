import logging

log_level = logging.DEBUG

def get_logger(name):
    log = logging.getLogger(name)
    log.setLevel(log_level)
    formatter = logging.Formatter(fmt="%(asctime)s %(levelname)s %(name)s: %(message)s", 
                            datefmt="%Y-%m-%d - %H:%M:%S")
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    log.addHandler(ch)
    return log