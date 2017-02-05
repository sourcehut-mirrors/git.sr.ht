import logging

try:
    from configparser import ConfigParser
except ImportError:
    # Python 2 support
    from ConfigParser import ConfigParser

logger = logging.getLogger("sr.ht")
logger.setLevel(logging.DEBUG)

sh = logging.StreamHandler()
sh.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
sh.setFormatter(formatter)

logger.addHandler(sh)

config = ConfigParser()
config.readfp(open('config.ini'))

cfg = lambda s, k: config.get(s, k)
cfgi = lambda s, k: int(cfg(s, k))
