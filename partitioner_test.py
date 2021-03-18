from quantum_job import Modification_Type, QuantumJob
from qiskit.circuit.quantumcircuit import QuantumCircuit
from qiskit.circuit.random.utils import random_circuit
from partitioner.partitioner import Partitioner
from qiskit_helper_functions.non_ibmq_functions import generate_circ

if __name__ == "__main__":
    max_subcircuit_qubit = 5
    circuit_type = 'supremacy'
    full_circ_size = 6
    #circuit = generate_circ(full_circ_size=full_circ_size,circuit_type=circuit_type)
    circuit = random_circuit(full_circ_size, 5, 2)
    print(circuit)
    job = QuantumJob(circuit, Modification_Type.none)
    part = Partitioner(None, None, {}, max_subcircuit_qubit, max_separate_circuits=4, max_cuts=10, verbose=True)
    sub_jobs = part._cut_job(job)
    print("fertig")