from execution_handler.execution_handler import ExecutionHandler
from quantum_job import QuantumJob

from queue import Queue

from qiskit import IBMQ
from qiskit.circuit.random import random_circuit



if __name__ == "__main__":

    input = Queue()

    output = Queue()

    provider = IBMQ.load_account()

    backend = provider.get_backend('ibmq_athens')

    backend_sim = provider.get_backend('ibmq_qasm_simulator')


    exec_handler = ExecutionHandler(backend_sim, input, output)

    for i in range(10):
        input.put(QuantumJob(random_circuit(5, 5, measure=True), shots=10000))
 
    while True:
        job = output.get()
        r = job.result
        print(job.id, r.success)


