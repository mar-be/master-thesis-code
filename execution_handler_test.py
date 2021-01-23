from qpu_connector.scheduler import ExecutionHandler

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

    for i in range(900):
        input.put({"circuit":random_circuit(5, 5 , measure=True), "shots":10000})

    for i in range(900):
        r = output.get()
        print(i, r.get_counts())


