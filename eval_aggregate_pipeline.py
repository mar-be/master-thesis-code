from queue import Queue

from qiskit.providers.aer import Aer, AerJob

from execution_handler.execution_handler import ExecutionHandler
from aggregator.aggregator import Aggregator, AggregatorResults
from qiskit import IBMQ, execute
from quantum_job import QuantumJob
from qiskit.circuit.random import random_circuit
from evaluate.metrics import chi_2_diff
from evaluate.util import sv_to_probability, counts_to_probability

from logger import get_logger

if __name__ == "__main__":

    log = get_logger("Evaluate")

    input_pipeline = Queue()
    input_exec = Queue()
    output_exec = Queue()
    output_pipline = Queue()

    provider = IBMQ.load_account()

    # backend = provider.get_backend('ibmq_athens')

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


    

    backend_sim = provider.get_backend('ibmq_qasm_simulator')


    exec_handler = ExecutionHandler(backend_sim, input_exec, output_exec)


    log.info("Started the ExecutionHandler and added the circuits")
    

    results = []
    agg_results = []

    for i in range(n_circuits):
        job = output_exec.get()
        results.append(job.result)
    
    log.info("All results for not aggregated circuits are available")

    agg_job_dict = {}

    aggregator = Aggregator(input_pipeline, input_exec, agg_job_dict, 10)
    aggregator.start()

    aggregator_results = AggregatorResults(output_exec, output_pipline, agg_job_dict)
    aggregator_results.start()

    log.info("Started the Aggrgator pipeline")

    for i in range(n_circuits):
        job = output_pipline.get()
        agg_results.append(job.result)
    
    log.info("All results for aggregated circuits are available")

    sv_res = sv_job.result()
    sv_results = [sv_res.get_statevector(circ) for circ in circuits]
    sv_res_prob = [sv_to_probability(sv) for sv in sv_results]

    res_prob = [counts_to_probability(r.get_counts(), n_qubits) for r in results]
    agg_res_prob = [counts_to_probability(r.get_counts(), n_qubits) for r in agg_results]

    for i in range(n_circuits):
        log.info(chi_2_diff(agg_res_prob[i], res_prob[i], sv_res_prob[i]))