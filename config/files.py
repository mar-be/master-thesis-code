from typing import Dict
from config.json_util import write_json

CONFIG_PATH = "./config.json"

example_config = {
    "IBMQ":{
        "token":"Insert your token here or delete this key-value pair to use the default token of your system."
    },
    "logger":{
        "level":"INFO"
    },
    "quantum_resource_mapper":{
        "backend_chooser":{
            "backend_black_list":["simulator_mps", "simulator_extended_stabilizer", "simulator_statevector", "simulator_stabilizer"],
            "backend_white_list":[],
            "allow_simulator":False,
            "number_of_qubits":{
                "min":None,
                "max":None
            },
            "quantum_volume":{
                "min":None,
                "max":None
            }
        },
        "execution_types":{
            "raw":True,
            "aggregation":True,
            "partition":True
        },
        "optimization_goal":"Either pick: 'high_throughput' or 'low_waiting_time'. The default value 'high_throughput' gets chosen, if the given value does not match."
    },
    "aggregator":{
        "timeout":10
    },
    "partitioner":{
        "max_separate_circuits":4,
        "max_cuts":10,
    },
    "execution_handler":{
        "transpile_timeout":20,
        "batch_timeout":60,
        "submitter_defer_interval":30, 
        "retrieve_interval":30,
        "provide_memory":False
    }
}

def generate_file(config:Dict=example_config, path:str=CONFIG_PATH) -> Dict:
    write_json(config, path)
    return config