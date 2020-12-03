import numpy as np
from qiskit import(
  QuantumCircuit,
  execute,
  IBMQ)
from qiskit.visualization import plot_histogram

def aggregate(list_of_circuits: list[QuantumCircuit]) -> QuantumCircuit:
    num_qubits = 0
    num_clbits = 0
    for circ in list_of_circuits:
        num_qubits += len(circ.qubits)
        num_clbits += len(circ.clbits)
    
    agg_circuit = QuantumCircuit(num_qubits, num_clbits)

    qubit_count = 0
    clbit_count = 0

    for circ in list_of_circuits:
        qubits = range(qubit_count, qubit_count + len(circ.qubits))
        clbits = range(clbit_count, clbit_count + len(circ.clbits))
        agg_circuit.compose(circ, qubits=qubits, clbits=clbits, inplace=True)
        qubit_count += len(circ.qubits)
        clbit_count += len(circ.clbits)

    return agg_circuit


# IBMQ.save_account('f5865210c4c93e8a0b5230c96a2cc402ad8c603c92641a1655b9f8c729ebf3ab4899db914dcd6aa8b75cd0849e34d5fc0f74adcd856d0d09da6aafc217d86bd4')
provider = IBMQ.load_account()
backend = provider.get_backend('ibmq_qasm_simulator')


# Create a Quantum Circuit acting on the q register
circuit = QuantumCircuit(2, 2)

# Add a H gate on qubit 0
circuit.h(0)

# Add a CX (CNOT) gate on control qubit 0 and target qubit 1
circuit.cx(0, 1)

# Map the quantum measurement to the classical bits
circuit.measure([0,1], [0,1])

# Create a Quantum Circuit acting on the q register
circuit_2 = QuantumCircuit(2, 2)

# Add a H gate on qubit 0
circuit_2.h(0)

# Map the quantum measurement to the classical bits
circuit_2.measure([0,1], [0,1])

print(circuit)
print(circuit_2)

agg_circuit = aggregate([circuit, circuit_2])

print(agg_circuit)

# Execute the circuit on the qasm simulator
job = execute(agg_circuit, backend, shots=1000)

# Grab results from the job
result = job.result()

# Returns counts
counts = result.get_counts(agg_circuit)
print("\nTotal count for 00 and 11 are:",counts)

# Draw the circuit
circuit.draw()

