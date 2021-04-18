import time
from evaluate.circuit_gen import circ_gen
import itertools
import json
import math
import os
from datetime import date, datetime
from logging import raiseExceptions

from qiskit.circuit.library.grover_operator import GroverOperator
from partitioner.partition_result_processing import ResultProcessing, ResultWriter
from partitioner.partitioner import Partitioner
from queue import Queue
from typing import List

import numpy as np
from qiskit import IBMQ, execute
from qiskit.circuit.quantumcircuit import QuantumCircuit
from qiskit.circuit.random import random_circuit
from qiskit.providers.aer import Aer, AerJob
from qiskit.providers.models import backendproperties
from qiskit.circuit.library import QFT

from aggregator.aggregator import Aggregator, AggregatorResults
from analyzer.backend_chooser import Backend_Data
from analyzer.result_analyzer import ResultAnalyzer
from evaluate.metrics import (chi_square, kullback_leibler_divergence,
                              metric_diff)
from evaluate.util import counts_to_probability, dict_to_array, sv_to_probability
from execution_handler.execution_handler import ExecutionHandler
import logger
from quantum_circuit_generator.generators import gen_BV, gen_adder, gen_grover, gen_hwea, gen_uccsd, gen_supremacy
from quantum_job import QuantumJob
import ibmq_account
import config.load_config as cfg

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, complex):
        return str(obj)
    raise TypeError ("Type %s not serializable" % type(obj))

def get_all_permutations(input_list):
    return list(itertools.chain(*itertools.permutations(input_list)))


def write_file(dir_path, backend, results, part_results, sv_res_prob: List[np.ndarray], n_qubits: int, circuits, circuit_type, subcircuit_max_qubits, shots):
    res_prob = [dict_to_array(r, n_qubits) for r in results]
    part_res_prob = [dict_to_array(r, n_qubits) for r in part_results]

    data = []
    n_circuits = len(circuits)
    for i in range(n_circuits):
        data.append({"circuit":circuits[i].qasm(), "sv-result":sv_res_prob[i].tolist(), "result":res_prob[i].tolist(), "part-result":part_res_prob[i].tolist()})

    backend_dict = {"name":backend.name()}
    if backend.configuration() != None:
        backend_dict["config"] = backend.configuration().to_dict() 
    
    if backend.status() != None:
        backend_dict["status"] = backend.status().to_dict()

    if backend.properties() != None:
        backend_dict["properties"] = backend.properties().to_dict()

    now = datetime.now()
    now_str = now.strftime('%Y-%m-%d-%H-%M-%S')
    with open(f'{dir_path}/{backend.name()}/{backend.name()}_{circuit_type}_{subcircuit_max_qubits}.json', 'w') as f:
        json.dump({"date":now_str, "circuit_type":circuit_type, "n_circuits":n_circuits, "n_qubits":n_qubits, "subcircuit_max_qubits":subcircuit_max_qubits, "shots":shots, "backend":backend_dict, "data":data}, f, indent=4, default=json_serial)

    log.info("Wrote results to file.")


if __name__ == "__main__":


    config = cfg.load_or_create()
    logger.set_log_level_from_config(config)
    provider = ibmq_account.get_provider(config)

    log = logger.get_logger("Evaluate")

    # backend_names = ['ibmq_qasm_simulator' , 'ibmq_athens', 'ibmq_santiago', 'ibmq_belem']
    # backend_names = ['ibmq_qasm_simulator' , 'ibmq_athens', 'ibmq_santiago', 'ibmq_quito', 'ibmq_lima', 'ibmq_belem']
    # backend_names = ['ibmq_qasm_simulator' , 'ibmq_athens', 'ibmq_santiago', 'ibmq_lima', 'ibmq_belem']
    backend_names = ['ibmq_qasm_simulator']
    circuit_types = ['bv', 'supremacy_linear']
    shots = 8192

    n_circuits = 1
    n_qubits = 5
    subcircuit_max_qubits = [4, 3, 2]

    now = datetime.now()
    now_str = now.strftime('%Y-%m-%d-%H-%M-%S')
    dir_path = f"part_data/{now_str}"

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
    part_results = Queue()
    all_results_are_available = Queue()
    output_pipline = Queue()
    errors = Queue()

    for backend_data in backend_data_list:
        for type in circuit_types:
            for circ in circuits[type]:
                for qubits in subcircuit_max_qubits:
                    input_pipeline.put(QuantumJob(circuit=circ.measure_all(inplace=False), shots=shots, backend_data=backend_data, config={"partitioner":{"subcircuit_max_qubits":qubits}}))
                    input_exec.put(QuantumJob(circuit=circ.measure_all(inplace=False), shots=shots, backend_data=backend_data))



    partition_dict = {}

    partitioner = Partitioner(input=input_pipeline, output=input_exec, partition_dict=partition_dict, error_queue=errors, **config["partitioner"])
    partitioner.start()

    while not input_pipeline.empty():
        time.sleep(10)
    log.info("Partitioned all circuits")

    exec_handler = ExecutionHandler(provider, input=input_exec, output=output_exec, batch_timeout=5)
    

    exec_handler._transpiler.start()

    time.sleep(5)

    while exec_handler._transpiler._any_pending_transpilation() or len(exec_handler._transpiler._timers)>0:
        time.sleep(10)
    log.info("Transpiled all circuits")

    exec_handler._batcher.start()

    while not exec_handler._batcher._input.empty():
        time.sleep(10)
    log.info("Added all circuits to batches")


    exec_handler._submitter.start()
    exec_handler._retriever.start()

    while not exec_handler._submitter._input.empty():
        time.sleep(10)
    log.info("All circuits ready to submit")

    exec_handler._processor.start()


    result_analyzer = ResultAnalyzer(input=output_exec, output=output_pipline, output_agg=None, output_part=part_results)
    result_analyzer.start()

    partition_result_writer = ResultWriter(input=part_results, completed_jobs=all_results_are_available, partition_dict=partition_dict)
    partition_result_writer.start()
    partition_result_processor = ResultProcessing(input=all_results_are_available, output=output_pipline, partition_dict=partition_dict)
    partition_result_processor.start()

    log.info("Started the partition pipeline")

    result_counter = {}
    results = {}
    part_results = {}


    n_results = 2*len(subcircuit_max_qubits)*n_circuits*len(backend_names)*len(circuits)

    for backend_name in backend_names:
        result_counter[backend_name] = 0
        results[backend_name] = {}
        part_results[backend_name] = {}
        for type in circuit_types:
            results[backend_name][type] = {}
            part_results[backend_name][type] = {}
            for qubits in subcircuit_max_qubits:
                results[backend_name][type][qubits] = []
                part_results[backend_name][type][qubits] = []



    for i in range(n_results):
        job = output_pipline.get()
        r = job.result_prob
        backend_name = job.backend_data.name
        count = result_counter[backend_name]
        count_qubits = count % (len(subcircuit_max_qubits)*n_circuits)
        qubits_index = int(count_qubits/n_circuits)
        qubits = subcircuit_max_qubits[qubits_index]
        count_type = count % (len(circuit_types)*len(subcircuit_max_qubits)*n_circuits)
        type_index = int(count_type/(n_circuits*len(subcircuit_max_qubits)))
        type = circuit_types[type_index]
        log.debug(f"{i}: Got job {job.id},type {job.type}, from backend {backend_name}, circuit type {type}, qubits {qubits}")
        result_counter[backend_name] += 1
        if len(results[backend_name][type][qubits]) < n_circuits:
            results[backend_name][type][qubits].append(r)
        else:
            part_results[backend_name][type][qubits].append(r)
        if len(results[backend_name][type][qubits]) == n_circuits and len(part_results[backend_name][type][qubits]) == 0:
            log.info(f"All results for not partitioned circuits {type}/{qubits} are available for backend {backend_name}")
        elif len(part_results[backend_name][type][qubits]) == n_circuits:
            log.info(f"All results for partitioned circuits {type}/{qubits} are available for backend {backend_name}")
            write_file(dir_path, backends[backend_name]["backend"], results[backend_name][type].pop(qubits), part_results[backend_name][type].pop(qubits), sv_results[type], n_qubits, circuits[type], type, qubits, shots)





