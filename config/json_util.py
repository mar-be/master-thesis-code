import json
from typing import Dict

def write_json(config:Dict, config_filepath:str):
    with open(config_filepath, "w") as file:
        json.dump(config, file, indent=4)

def read_json(config_filepath:str) -> Dict:
    with open(config_filepath) as file:
        return json.load(file)