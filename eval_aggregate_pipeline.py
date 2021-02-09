from queue import Queue
import pickle
import json
from datetime import datetime, date

from qiskit.providers.aer import Aer, AerJob
from qiskit.providers.models import backendproperties

from execution_handler.execution_handler import ExecutionHandler
from aggregator.aggregator import Aggregator, AggregatorResults
from qiskit import IBMQ, execute
from quantum_job import QuantumJob
from qiskit.circuit.random import random_circuit
from evaluate.metrics import chi_2_diff
from evaluate.util import sv_to_probability, counts_to_probability
from analyzer.result_analyzer import ResultAnalyzer

from logger import get_logger

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))

if __name__ == "__main__":

    log = get_logger("Evaluate")

    input_pipeline = Queue()
    input_exec = Queue()
    output_exec = Queue()
    agg_results = Queue()
    output_pipline = Queue()

    provider = IBMQ.load_account()

    backend = provider.get_backend('ibmq_santiago')
    # backend = provider.get_backend('ibmq_qasm_simulator')

    n_circuits = 100
    n_qubits = 2

    circuits = [random_circuit(n_qubits, 5, measure=False) for i in range(n_circuits)]

    log.info(f"Generated {n_circuits} random circuits")

    statevector_backend = Aer.get_backend('statevector_simulator')
    sv_job:AerJob = execute(circuits, statevector_backend)

    log.info("Executed the circuits with local statevector simulator")


    for circ in circuits:
        input_pipeline.put(QuantumJob(circuit=circ.measure_all(inplace=False), shots=8192))
        input_exec.put(QuantumJob(circuit=circ.measure_all(inplace=False), shots=8192))



    agg_job_dict = {}

    aggregator = Aggregator(input=input_pipeline, output=input_exec, job_dict=agg_job_dict, timeout=10)
    aggregator.start()

    exec_handler = ExecutionHandler(backend, input=input_exec, results=output_exec)

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

    sv_res = sv_job.result()
    sv_results = [sv_res.get_statevector(circ) for circ in circuits]
    sv_res_prob = [sv_to_probability(sv) for sv in sv_results]

    res_prob = [counts_to_probability(r.get_counts(), n_qubits) for r in results]
    agg_res_prob = [counts_to_probability(r.get_counts(), n_qubits) for r in agg_results]

    data = []
    for i in range(n_circuits):
        c2 = chi_2_diff(agg_res_prob[i], res_prob[i], sv_res_prob[i])
        log.info(c2)
        data.append({"circuit":circuits[i].qasm(), "sv-result":sv_res_prob[i].tolist(), "result":res_prob[i].tolist(), "agg-result":agg_res_prob[i].tolist(), "chi^2-diff":c2})

    backend_dict = {"name":backend.name()}
    if backend.configuration() != None:
        backend_dict["config"] = backend.configuration().to_dict() 
    
    if backend.status() != None:
        backend_dict["status"] = backend.status().to_dict()

    if backend.properties() != None:
        backend_dict["properties"] = backend.properties().to_dict()

    now = datetime.now()
    now_str = now.strftime('%Y-%m-%d-%H-%M-%S')
    with open(f'agg_data/{now_str}.json', 'w') as f:
        json.dump({"backend":backend_dict, "data":data}, f, indent=4, default=json_serial)