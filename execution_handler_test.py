from execution_handler.execution_handler import ExecutionHandler
from quantum_job import QuantumJob

from queue import Queue

from qiskit import IBMQ
from qiskit.circuit.random import random_circuit
import logger

log = logger.get_logger("Test")

if __name__ == "__main__":

    input = Queue()

    output = Queue()

    provider = IBMQ.load_account()

    # backend = provider.get_backend('ibmq_athens')

    # backend_sim = provider.get_backend('ibmq_qasm_simulator')


    exec_handler = ExecutionHandler(provider, input, output, 5)
    exec_handler.start()

    for i in range(300):
        input.put(QuantumJob(random_circuit(5, 5, measure=True), shots=10000, backend="ibmq_qasm_simulator"))
        # if i % 2 == 0:
        #     input.put(QuantumJob(random_circuit(5, 5, measure=True), shots=10000, backend="ibmq_athens"))
        # else:
        #     input.put(QuantumJob(random_circuit(5, 5, measure=True), shots=10000, backend="ibmq_santiago"))
        
    
    i = 0
    while True:
        job = output.get()
        r = job.result
        log.info(f"{i}: Got job {job.id}, success: {r.success}")
        i+=1


