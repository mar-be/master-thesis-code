import copy
from qiskit import QuantumCircuit
from qiskit.circuit.random import random_circuit
from quantum_ciruit_object import QC_Object, Modification, session

def aggregate(list_of_circuits: list[QuantumCircuit]) -> QuantumCircuit:
    num_qubits = 0
    num_clbits = 0
    num_ancillas = 0
    agg_circuit = QuantumCircuit()
    for index, circ in enumerate(list_of_circuits):
        registers = []
        for qubit in circ.qubits:
            if not qubit.register in registers:
                registers.append(qubit.register)
        for clbit in circ.clbits:
            if not clbit.register in registers:
                registers.append(clbit.register)
        for reg in registers:
            reg_copy = copy.deepcopy(reg)
            reg_copy.name = reg.name + "_" + str(index)
            agg_circuit.add_register(reg_copy)
    
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
    
    circ1 = random_circuit(10, 10, measure=True)
    circ2 = random_circuit(10, 10, measure=True)
    
    qc_obj_1 = QC_Object(circ1)
    qc_obj_2 = QC_Object(circ2)

    agg = aggregate_qc_obj([qc_obj_1, qc_obj_2])

    print(len(agg.modification_output.input_circuit))

