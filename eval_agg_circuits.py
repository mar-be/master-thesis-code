import json
from typing import List
from resource_mapping.result_analyzer import ResultAnalyzer
from execution_handler.execution_handler import ExecutionHandler
from aggregator.aggregator import Aggregator, AggregatorResults
from datetime import datetime, date
from quantum_execution_job import QuantumExecutionJob
from queue import Queue
from evaluate.util import counts_to_probability, sv_to_probability

import numpy as np

from qiskit import execute
from evaluate.circuit_gen import circ_gen
import os
import ibmq_account
import config.load_config as cfg
from resource_mapping.backend_chooser import Backend_Data
import logger 
from qiskit.providers.aer import Aer, AerJob   


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, complex):
        return str(obj)
    raise TypeError ("Type %s not serializable" % type(obj))

def write_file(dir_path, backend, results, agg_results, sv_res_prob: List[np.ndarray], n_qubits: int, circuits, circuit_type, shots):
    res_prob = [counts_to_probability(r.get_counts(), n_qubits) for r in results]
    agg_res_prob = [counts_to_probability(r.get_counts(), n_qubits) for r in agg_results]

    data = []
    n_circuits = len(circuits)
    for i in range(n_circuits):
        data.append({"circuit":circuits[i].qasm(), "sv-result":sv_res_prob[i].tolist(), "result":res_prob[i].tolist(), "agg-result":agg_res_prob[i].tolist()})

    backend_dict = {"name":backend.name()}
    if backend.configuration() != None:
        backend_dict["config"] = backend.configuration().to_dict() 
    
    if backend.status() != None:
        backend_dict["status"] = backend.status().to_dict()

    if backend.properties() != None:
        backend_dict["properties"] = backend.properties().to_dict()

    now = datetime.now()
    now_str = now.strftime('%Y-%m-%d-%H-%M-%S')
    with open(f'{dir_path}/{backend.name()}/{backend.name()}_{circuit_type}.json', 'w') as f:
        json.dump({"date":now_str, "circuit_type":circuit_type, "n_circuits":n_circuits, "n_qubits":n_qubits, "shots":shots, "backend":backend_dict, "data":data}, f, indent=4, default=json_serial)

    log.info("Wrote results to file.")

if __name__ == "__main__":
    """
    Configure the evaluation here:
    """
    # backend_names = ['ibmq_qasm_simulator' , 'ibmq_athens', 'ibmq_santiago', 'ibmq_belem']
    # backend_names = ['ibmq_qasm_simulator' , 'ibmq_athens', 'ibmq_santiago', 'ibmq_quito', 'ibmq_lima', 'ibmq_belem']
    backend_names = ['ibmq_qasm_simulator']
    circuit_types = ["grover", "bv", "qft", "hwea", "uccsd", "supremacy_linear"]

    shots = 8192
    n_circuits = 2
    n_qubits = 2

    """
    Configuration End
    """


    config = cfg.load_or_create()
    logger.set_log_level_from_config(config)
    provider = ibmq_account.get_provider(config)

    log = logger.get_logger("Evaluate")


    now = datetime.now()
    now_str = now.strftime('%Y-%m-%d-%H-%M-%S')
    dir_path = f"agg_data_circ/{now_str}"
    os.makedirs(dir_path)

    log.info(f"Created directory {dir_path}")

    circuits = {}

    for type in circuit_types:
        circ, _ = circ_gen(type, n_qubits, 1)
        circ = circ[0]
        circuits[type] = circ

    log.info(f"Generated circuits for the types: {circuit_types}")

    statevector_backend = Aer.get_backend('statevector_simulator')

    sv_results = {}
    for type, circ in circuits.items():
        sv_job:AerJob = execute(circ, statevector_backend)
        sv_res = sv_job.result()
        sv_result = sv_res.get_statevector(circ)
        sv_results[type] = sv_to_probability(sv_result)

    log.info("Executed the circuits with local statevector simulator")

    backend_data_list = []
    backends = {}
    for backend_name in backend_names:
        backend = provider.get_backend(backend_name)
        backend_data = Backend_Data(backend)
        backend_data_list.append(backend_data)
        backends[backend_name] = {"backend":backend, "backend_data":backend_data}
        os.makedirs(f"{dir_path}/{backend.name()}")

    for type in circuit_types:
        circuits[type] = [circuits[type]]*n_circuits
        sv_results[type] = [sv_results[type]]*n_circuits

    input_pipeline = Queue()
    input_exec = Queue()
    output_exec = Queue()
    agg_results = Queue()
    output_pipline = Queue()


    for backend_data in backend_data_list:
        for type in circuit_types:
            for circ in circuits[type]:
                input_pipeline.put(QuantumExecutionJob(circuit=circ.measure_all(inplace=False), shots=shots, backend_data=backend_data))
                input_exec.put(QuantumExecutionJob(circuit=circ.measure_all(inplace=False), shots=shots, backend_data=backend_data))

    agg_job_dict = {}

    aggregator = Aggregator(input=input_pipeline, output=input_exec, job_dict=agg_job_dict, timeout=10)
    aggregator.start()

    exec_handler = ExecutionHandler(provider, input=input_exec, output=output_exec, batch_timeout=5)
    exec_handler.start()

    result_analyzer = ResultAnalyzer(input=output_exec, output=output_pipline, output_agg=agg_results, output_part=None)
    result_analyzer.start()

    aggregator_results = AggregatorResults(input=agg_results, output=output_pipline, job_dict=agg_job_dict)
    aggregator_results.start()

    log.info("Started the Aggrgator pipeline")

    result_counter = {}
    results = {}
    agg_results = {}

    n_results = 2*n_circuits*len(backend_names)*len(circuits)

    for backend_name in backend_names:
        result_counter[backend_name] = 0
        results[backend_name] = {}
        agg_results[backend_name] = {}
        for type in circuit_types:
            results[backend_name][type] = []
            agg_results[backend_name][type] = []

    

    for i in range(n_results):
        job = output_pipline.get()
        r = job.result
        backend_name = job.backend_data.name
        log.debug(f"{i}: Got job {job.id},type {job.type}, from backend {backend_name}, success: {r.success}")
        count = result_counter[backend_name]
        count = count % (len(circuit_types)*n_circuits)
        type_index = int(count/n_circuits)
        type = circuit_types[type_index]
        result_counter[backend_name] += 1
        if len(results[backend_name][type]) < n_circuits:
            results[backend_name][type].append(r)
        else:
            agg_results[backend_name][type].append(r)
        if len(results[backend_name][type]) == n_circuits and len(agg_results[backend_name][type]) == 0:
            log.info(f"All results for not aggregated circuits {type} are available for backend {backend_name}")
        elif len(agg_results[backend_name][type]) == n_circuits:
            log.info(f"All results for aggregated circuits {type} are available for backend {backend_name}")
            write_file(dir_path, backends[backend_name]["backend"], results[backend_name].pop(type), agg_results[backend_name].pop(type), sv_results[type], n_qubits, circuits[type], type, shots)