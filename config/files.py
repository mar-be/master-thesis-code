from typing import Dict
from config.json_util import write_json

CONFIG_PATH = "./config.json"

example_config = {
    "IBMQ":{
        "token":"Insert here your token or delete this key-value pair to use your default token of your system."
    },
    "logger":{
        "level":"INFO"
    }
}

def generate_file(config:Dict=example_config, path:str=CONFIG_PATH) -> Dict:
    write_json(config, path)
    return config