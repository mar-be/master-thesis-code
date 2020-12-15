from qiskit import QuantumCircuit
from quantum_ciruit_object import QC_Object, Modification, session

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

def aggregate_qc_obj(list_of_circuits: list[QC_Object]) -> QC_Object:
    agg_circuit = aggregate([qc_obj.circuit for qc_obj in list_of_circuits])
    agg_qc_obj = QC_Object(agg_circuit)
    agg_mod = Modification()
    agg_mod.input_circuit.extend(list_of_circuits)
    agg_mod.output_circuit.append(agg_qc_obj)
    agg_mod.type = "aggregation"
    session.add(agg_mod)
    session.commit()
    return agg_qc_obj


if __name__ == "__main__":
    # Create a Quantum Circuit acting on the q register
    circuit = QuantumCircuit(2, 2)

    # Add a H gate on qubit 0
    circuit.h(0)

    # Add a CX (CNOT) gate on control qubit 0 and target qubit 1
    circuit.cx(0, 1)

    # Map the quantum measurement to the classical bits
    circuit.measure([0,1], [0,1])

    qc_obj = QC_Object.from_qasm(circuit.qasm())

    # Create a Quantum Circuit acting on the q register
    circuit_2 = QuantumCircuit(2, 2)

    # Add a H gate on qubit 0
    circuit_2.h(0)

    # Map the quantum measurement to the classical bits
    circuit_2.measure([0,1], [0,1])


    qc_obj_2 = QC_Object(circuit_2)

    agg = aggregate_qc_obj([qc_obj, qc_obj_2])

    print(len(agg.modification_output.input_circuit))

