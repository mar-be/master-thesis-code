import copy
from typing import List, Any
from qiskit import QuantumCircuit
from qiskit.circuit.random import random_circuit
from qiskit.result import Result
from quantum_ciruit_object import Quantum_Job, Modification, session

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
            reg_copy.name =  f"circ{index}reg{reg.name}"
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

def aggregate_qc_obj(list_of_circuits: list[Quantum_Job]) -> Quantum_Job:
    agg_circuit = aggregate([qc_obj.circuit for qc_obj in list_of_circuits])
    agg_qc_obj = Quantum_Job(agg_circuit)
    agg_mod = Modification()
    agg_mod.input_circuit.extend(list_of_circuits)
    agg_mod.output_circuit.append(agg_qc_obj)
    agg_mod.type = "aggregation"
    session.add(agg_mod)
    session.commit()
    return agg_qc_obj

def results(result: Result, job: Quantum_Job) -> List[Result]:
    results = []
    for job_item in job.modification_input().input_circuit():
        job_result = __calc_results(job_item, result.results)
        results.append(Result(result.backend_name, result.backend_version, job_item.id, job_item.job, result.success, job_result, result.date, result.status, result.header))
    return results

def __calc_results(job_item:Quantum_Job, result:Any) -> Any:
    pass

if __name__ == "__main__":
    
    circ1 = random_circuit(10, 10, measure=True)
    circ2 = random_circuit(10, 10, measure=True)
    
    qc_obj_1 = Quantum_Job(circ1)
    qc_obj_2 = Quantum_Job(circ2)

    agg = aggregate_qc_obj([qc_obj_1, qc_obj_2])


