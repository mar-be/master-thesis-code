import itertools
import json
import math
import os
from datetime import date, datetime
from logging import raiseExceptions
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
from evaluate.util import counts_to_probability, sv_to_probability
from execution_handler.execution_handler import ExecutionHandler
from logger import get_logger
from quantum_circuit_generator.generators import gen_adder, gen_hwea, gen_uccsd, gen_supremacy
from quantum_job import QuantumJob


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, complex):
        return str(obj)
    raise TypeError ("Type %s not serializable" % type(obj))

def random_circuits(n_qubits, n_circuits, depth=5):
    return [random_circuit(n_qubits, depth, measure=False) for i in range(n_circuits)], n_circuits

def adder_circuits(n_qubits):
    nbits=int((n_qubits-2)/2)
    n_circuits = 2**(2*nbits)
    return [gen_adder(nbits=nbits, a=a, b=b) for a in range(2**nbits) for b in range(2**nbits)], n_circuits

def growing_depth(n_qubits, n_circuits):
    circuits = []
    circ = QuantumCircuit(n_qubits)
    for i in range(n_circuits):
        circ = random_circuit(n_qubits, 1, measure=False).combine(circ)
        circuits.append(circ)
    return circuits, n_circuits

def hwea(n_qubits, n_circuits, depth=5):
    return [gen_hwea(n_qubits, depth) for i in range(n_circuits)], n_circuits

def uccsd(n_qubits, n_circuits):
    return [gen_uccsd(n_qubits) for i in range(n_circuits)], n_circuits

def qft(n_qubits, n_circuits):
    return [QFT(num_qubits=n_qubits, approximation_degree=0, do_swaps=False) for i in range(n_circuits)], n_circuits

def aqft(n_qubits, n_circuits):
    approximation_degree=int(math.log(n_qubits,2)+2)
    return [QFT(num_qubits=n_qubits, approximation_degree=n_qubits-approximation_degree,do_swaps=False) for i in range(n_circuits)], n_circuits

def supremacy_linear(n_qubits, n_circuits, depth=8):
    return [gen_supremacy(1, n_qubits, depth, regname='q') for i in range(n_circuits)], n_circuits


def get_all_permutations(input_list):
    return list(itertools.chain(*itertools.permutations(input_list)))

def write_file(dir_path, backend, results, agg_results, sv_res_prob: List[np.ndarray], n_qubits: int, circuits, circuit_type, permute, shots):
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
    with open(f'{dir_path}/{backend.name()}.json', 'w') as f:
        json.dump({"date":now_str, "circuit_type":circuit_type, "n_circuits":n_circuits, "n_qubits":n_qubits, "permute":permute, "shots":shots, "backend":backend_dict, "data":data}, f, indent=4, default=json_serial)

    log.info("Wrote results to file.")


if __name__ == "__main__":

    log = get_logger("Evaluate")

    input_pipeline = Queue()
    input_exec = Queue()
    output_exec = Queue()
    agg_results = Queue()
    output_pipline = Queue()

    provider = IBMQ.load_account()

    # backend = provider.get_backend('ibmq_athens')
    # backend = provider.get_backend('ibmq_santiago')
    # backend = provider.get_backend('ibmq_16_melbourne')
    # backend = provider.get_backend('ibmq_quito')
    # backend = provider.get_backend('ibmq_qasm_simulator')
    
    backend_names = ['ibmq_qasm_simulator' , 'ibmq_athens', 'ibmq_santiago', 'ibmq_quito', 'ibmq_lima', 'ibmq_belem']
    # backend_names = ['ibmq_qasm_simulator']
    shots = 8192


    n_circuits = 100
    n_qubits = 2
    circuit_type = "qft"
    permute = False

    now = datetime.now()
    now_str = now.strftime('%Y-%m-%d-%H-%M-%S')
    dir_path = f"agg_data/{circuit_type}_{now_str}"

    os.mkdir(dir_path)

    log.info(f"Created directory {dir_path}")

    if circuit_type == "random":
        circuits, n_circuits = random_circuits(n_qubits, n_circuits)
    elif circuit_type == "adder":
        circuits, n_circuits = adder_circuits(n_qubits)
    elif circuit_type == "growing_depth":
        circuits, n_circuits = growing_depth(n_qubits, n_circuits)
    elif circuit_type == "hwea":
        circuits, n_circuits = hwea(n_qubits, n_circuits)
    elif circuit_type == "uccsd":
        circuits, n_circuits = uccsd(n_qubits, n_circuits)
    elif circuit_type == "aqft":
        circuits, n_circuits = aqft(n_qubits, n_circuits)
    elif circuit_type == "qft":
        circuits, n_circuits = qft(n_qubits, n_circuits)
    elif circuit_type == 'supremacy_linear':
        circuits, n_circuits = supremacy_linear(n_qubits, n_circuits)
    else:
        raise ValueError("Inappropiate circuit_type")

    log.info(f"Generated {n_circuits} circuits")

    statevector_backend = Aer.get_backend('statevector_simulator')

    sv_job:AerJob = execute(circuits, statevector_backend)
    sv_res = sv_job.result()
    sv_results = [sv_res.get_statevector(circ) for circ in circuits]
    sv_res_prob = [sv_to_probability(sv) for sv in sv_results]
    log.info("Executed the circuits with local statevector simulator")


    if permute:
        circuits = get_all_permutations(circuits)
        sv_res_prob = get_all_permutations(sv_res_prob)
        n_circuits = len(circuits)
        log.info(f"Generated all permutations. Now there are {n_circuits} circuits")

    backend_data_list = []
    backends = {}
    for backend_name in backend_names:
        backend = provider.get_backend(backend_name)
        backend_data = Backend_Data(backend)
        backend_data_list.append(backend_data)
        backends[backend_name] = {"backend":backend, "backend_data":backend_data}

    for backend_data in backend_data_list:
        for circ in circuits:
            input_pipeline.put(QuantumJob(circuit=circ.measure_all(inplace=False), shots=shots, backend_data=backend_data))
            input_exec.put(QuantumJob(circuit=circ.measure_all(inplace=False), shots=shots, backend_data=backend_data))




    agg_job_dict = {}

    aggregator = Aggregator(input=input_pipeline, output=input_exec, job_dict=agg_job_dict, timeout=10)
    aggregator.start()

    exec_handler = ExecutionHandler(provider, input=input_exec, output=output_exec)
    exec_handler.start()

    result_analyzer = ResultAnalyzer(input=output_exec, output=output_pipline, output_agg=agg_results, output_part=None)
    result_analyzer.start()

    aggregator_results = AggregatorResults(input=agg_results, output=output_pipline, job_dict=agg_job_dict)
    aggregator_results.start()

    log.info("Started the Aggrgator pipeline")

    results = {}
    agg_results = {}


    n_results = 2*n_circuits*len(backend_names)
    for backend_name in backend_names:
        results[backend_name] = []
        agg_results[backend_name] = []

    for i in range(n_results):
        job = output_pipline.get()
        r = job.result
        backend_name = job.backend_data.name
        log.debug(f"{i}: Got job {job.id},type {job.type}, from backend {backend_name}, success: {r.success}")
        if len(results[backend_name]) < n_circuits:
            results[backend_name].append(r)
        else:
            agg_results[backend_name].append(r)
        if len(results[backend_name]) == n_circuits and len(agg_results[backend_name]) == 0:
            log.info(f"All results for not aggregated circuits are available for backend {backend_name}")
        elif len(agg_results[backend_name]) == n_circuits:
            log.info(f"All results for aggregated circuits are available for backend {backend_name}")
            write_file(dir_path, backends[backend_name]["backend"], results.pop(backend_name), agg_results.pop(backend_name), sv_res_prob, n_qubits, circuits, circuit_type, permute, shots)




