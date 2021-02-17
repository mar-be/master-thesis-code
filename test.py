from datetime import datetime, timedelta
from analyzer.backend_chooser import Backend_Chooser, no_simulator_filter
from analyzer.circuit_analyzer import CircuitAnalyzer
from queue import Queue
from quantum_job import QuantumJob

if __name__ == "__main__":
    input = Queue()
    from qiskit import IBMQ
    provider = IBMQ.load_account()
    bc = Backend_Chooser(provider)
    # print("first round")
    # backends = bc.get_backends()
    # for name, dict in backends.items():
    #     print(name)
    #     print(dict)
    # print(bc.get_least_busy(filters=lambda x: x["n_qubits"]>=6 and no_simulator_filter(x)))

    # exit()
    ca = CircuitAnalyzer(input, None, None, None, bc)
    ca.start()
    from qiskit.circuit.random import random_circuit
    for i in range(1, 20):
        input.put(QuantumJob(random_circuit(i,i, measure=True)))