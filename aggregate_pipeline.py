from analyzer.backend_chooser import Backend_Data
from logger import get_logger
from queue import Queue
from execution_handler.execution_handler import ExecutionHandler
from aggregator.aggregator import Aggregator, AggregatorResults
from qiskit import IBMQ
from quantum_job import QuantumJob
from qiskit.circuit.random import random_circuit

if __name__ == "__main__":
    log = get_logger("Evaluate")
    input = Queue()
    output_agg = Queue()
    output_exec = Queue()
    output = Queue()

    provider = IBMQ.load_account()

    # backend = provider.get_backend('ibmq_athens')

    agg_job_dict = {}

    backend_sim = provider.get_backend('ibmq_qasm_simulator')
    backend = provider.get_backend('ibmq_quito')

    backend_data_1 = Backend_Data(backend_sim)
    backend_data_2 = Backend_Data(backend)

    aggregator = Aggregator(input, output_agg, agg_job_dict, 10)
    aggregator.start()

    exec_handler = ExecutionHandler(provider, output_agg, output_exec, batch_timeout=10)
    exec_handler.start()

    aggregator_results = AggregatorResults(output_exec, output, agg_job_dict)
    aggregator_results.start()

    for i in range(200):
        if i % 2 == 0:
            backend_data = backend_data_1
        else:
            backend_data = backend_data_2
        input.put(QuantumJob(random_circuit(2, 5, measure=True), shots=10000, backend_data=backend_data))
    
    i = 0
    while True:
        job = output.get()
        r = job.result
        log.info(f"{i}: Got job {job.id},type {job.type}, from backend {job.backend_data.name}, success: {r.success}")
        i += 1