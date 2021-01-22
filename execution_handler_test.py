from qpu_connector.execution_handler import Execution_Handler

from queue import Queue

from qiskit import IBMQ
from qiskit.circuit.random import random_circuit



if __name__ == "__main__":

    input = Queue()
    output = Queue()

    provider = IBMQ.load_account()

    backend = provider.get_backend('ibmq_athens')

    backend_sim = provider.get_backend('ibmq_qasm_simulator')


    exec_handler = Execution_Handler(backend_sim, input, output, 30)
    exec_handler.start()

    for i in range(1800):
        circ = {"circuit":random_circuit(5, 5 , measure=True), "shots":10000}
        input.put(circ)

    for i in range(1800):
        r = output.get()
        print(i, r.get_counts())


