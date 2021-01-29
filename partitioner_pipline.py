from queue import Queue
from execution_handler.scheduler import ExecutionHandler
from partitioner.partitioner import Partitioner
from qiskit import IBMQ
from quantum_job import QuantumJob
from qiskit.circuit.random import random_circuit

if __name__ == "__main__":
    input = Queue()
    output_part = Queue()
    output_exec = Queue()

    provider = IBMQ.load_account()

    # backend = provider.get_backend('ibmq_athens')

    part_job_dict = {}

    backend_sim = provider.get_backend('ibmq_qasm_simulator')

    part = Partitioner(input, output_part, part_job_dict, max_subcircuit_qubit=5, num_subcircuits=[2,3,4], max_cuts=10, verbose=True)
    part.start()

    exec_handler = ExecutionHandler(backend_sim, output_part, output_exec)


    
    input.put(QuantumJob(random_circuit(6, 5, 2), shots=10000))
    
    i = 0
    while True:
        job = output_exec.get()
        r = job.result
        print(i, job.id, r.success)
        i += 1