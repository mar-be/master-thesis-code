from analyzer.backend_chooser import Backend_Data
from queue import Queue
from execution_handler.execution_handler import ExecutionHandler
from partitioner.partitioner import Partitioner
from partitioner.partition_result_processing import ResultWriter, ResultProcessing
from qiskit import IBMQ
from quantum_job import QuantumJob
from qiskit.circuit.random import random_circuit
import logger

if __name__ == "__main__":
    input = Queue()
    output_part = Queue()
    output_exec = Queue()
    results_available = Queue()
    output = Queue()

    provider = IBMQ.load_account()

    backend = provider.get_backend('ibmq_qasm_simulator')
    # backend = provider.get_backend('ibmq_athens')

    part_job_dict = {}

    # backend = provider.get_backend('ibmq_belem')

    part = Partitioner(input, output_part, part_job_dict, num_subcircuits=[2,3,4], max_cuts=10)
    part.start()

    exec_handler = ExecutionHandler(provider, output_part, output_exec, batch_timeout=5)
    exec_handler.start()

    part_res = ResultWriter(output_exec, results_available, part_job_dict)
    part_res.start()

    part_processing = ResultProcessing(results_available, output, part_job_dict, True)
    part_processing.start()

    backend_data = Backend_Data(backend)
    
    input.put(QuantumJob(random_circuit(6, 5, 2), shots=10000, backend_data=backend_data))
    input.put(QuantumJob(random_circuit(6, 5, 2), shots=10000, backend_data=backend_data))

    log = logger.get_logger("Pipeline")
    i = 0
    while True:
        job = output.get() 
        log.info(f"{i} {job.id} {job.result_prob}")
        i += 1