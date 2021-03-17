from config.json_util import read_json
import config.files as cf

import logger

log = logger.get_logger(__name__)

def load_or_create():
    try:
        genral_config = read_json(cf.CONFIG_PATH)
        log.info(f"Loaded config from {cf.CONFIG_PATH}")
    except FileNotFoundError:
        genral_config = cf.generate_file()
        log.info(f"Created example config {cf.CONFIG_PATH}")
    return genral_config