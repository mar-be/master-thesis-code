from logging import raiseExceptions

from qiskit.circuit.quantumcircuit import QuantumCircuit
from quantum_circuit_generator.generators import gen_adder, gen_hwea, gen_uccsd
from queue import Queue
import itertools
import json
from datetime import datetime, date

from qiskit.providers.aer import Aer, AerJob
from qiskit.providers.models import backendproperties

from execution_handler.execution_handler import ExecutionHandler
from aggregator.aggregator import Aggregator, AggregatorResults
from qiskit import IBMQ, execute
from quantum_job import QuantumJob
from qiskit.circuit.random import random_circuit
from evaluate.metrics import metric_diff, chi_square, kullback_leibler_divergence
from evaluate.util import sv_to_probability, counts_to_probability
from analyzer.result_analyzer import ResultAnalyzer

from logger import get_logger

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


def get_all_permutations(input_list):
    return list(itertools.chain(*itertools.permutations(input_list)))


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
    backend = provider.get_backend('ibmq_16_melbourne')
    # backend = provider.get_backend('ibmq_quito')
    # backend = provider.get_backend('ibmq_qasm_simulator')
    


    n_circuits = 250
    n_qubits = 6
    circuit_type = "uccsd"
    permute = False

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

        


    for circ in circuits:
        input_pipeline.put(QuantumJob(circuit=circ.measure_all(inplace=False), shots=8192))
        input_exec.put(QuantumJob(circuit=circ.measure_all(inplace=False), shots=8192))



    agg_job_dict = {}

    aggregator = Aggregator(input=input_pipeline, output=input_exec, job_dict=agg_job_dict, timeout=10)
    aggregator.start()

    exec_handler = ExecutionHandler(backend, input=input_exec, results=output_exec, batch_timeout=5)

    result_analyzer = ResultAnalyzer(input=output_exec, output=output_pipline, output_agg=agg_results, output_part=None)
    result_analyzer.start()

    aggregator_results = AggregatorResults(input=agg_results, output=output_pipline, job_dict=agg_job_dict)
    aggregator_results.start()

    log.info("Started the Aggrgator pipeline")

    results = []
    agg_results = []

    for i in range(n_circuits):
        job = output_pipline.get()
        results.append(job.result)
    
    log.info("All results for not aggregated circuits are available")

    for i in range(n_circuits):
        job = output_pipline.get()
        agg_results.append(job.result)
    
    log.info("All results for aggregated circuits are available")


    res_prob = [counts_to_probability(r.get_counts(), n_qubits) for r in results]
    agg_res_prob = [counts_to_probability(r.get_counts(), n_qubits) for r in agg_results]

    data = []
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
    with open(f'agg_data/{circuit_type}_{backend.name()}_{now_str}.json', 'w') as f:
        json.dump({"backend":backend_dict, "circuit_type":circuit_type, "n_circuits":n_circuits, "n_qubits":n_qubits, "permute":permute, "data":data}, f, indent=4, default=json_serial)

    log.info("Wrote results to file.")