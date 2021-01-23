from qpu_connector.scheduler import SchedulerQueue

from queue import Queue

from qiskit import IBMQ
from qiskit.circuit.random import random_circuit



if __name__ == "__main__":

    output = Queue()

    provider = IBMQ.load_account()

    backend = provider.get_backend('ibmq_athens')

    backend_sim = provider.get_backend('ibmq_qasm_simulator')


    sq = SchedulerQueue(backend_sim, output)

    for i in range(3):
        circuits = {}
        for j in range(300):
            circuits[j] = {"circuit":random_circuit(5, 5 , measure=True), "shots":10000}
        sq.addCircuits(circuits)

    for i in range(900):
        r = output.get()
        print(i, r.get_counts())


