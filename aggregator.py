from qiskit import QuantumCircuit

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