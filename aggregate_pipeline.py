from queue import Queue
from execution_handler.execution_handler import ExecutionHandler
from aggregator.aggregator import Aggregator, AggregatorResults
from qiskit import IBMQ
from quantum_job import QuantumJob
from qiskit.circuit.random import random_circuit

if __name__ == "__main__":
    input = Queue()
    output_agg = Queue()
    output_exec = Queue()
    output = Queue()

    provider = IBMQ.load_account()

    # backend = provider.get_backend('ibmq_athens')

    agg_job_dict = {}

    backend_sim = provider.get_backend('ibmq_qasm_simulator')

    aggregator = Aggregator(input, output_agg, agg_job_dict, 10)
    aggregator.start()

    exec_handler = ExecutionHandler(backend_sim, output_agg, output_exec)

    aggregator_results = AggregatorResults(output_exec, output, agg_job_dict)
    aggregator_results.start()

    for i in range(900):
        input.put(QuantumJob(random_circuit(5, 5, measure=True), shots=10000))
    
    i = 0
    while True:
        job = output.get()
        r = job.result
        print(i, job.id, r.success)
        i += 1