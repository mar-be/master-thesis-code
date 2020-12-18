import copy
from typing import Dict, List, Any
from qiskit import QuantumCircuit
from qiskit.circuit import register
from qiskit.circuit.random import random_circuit
from qiskit.result import Result
from quantum_ciruit_object import Modification_Type, Quantum_Job, session


def aggregate_q_jobs(list_of_jobs: list[Quantum_Job]) -> Quantum_Job:
    agg_circuit = QuantumCircuit()
    aggregate_info = {}
    qreg_count = 0
    creg_count = 0
    qreg_order = {}
    creg_order = {}
    for index, job in enumerate(list_of_jobs):
        circ = job.circuit
        aggregate_info[job.id] = {}
        registers = []
        for qreg in circ.qregs:
            registers.append(qreg)
            qreg_order[f"circ{index}reg{qreg.name}"] = qreg_count
            qreg_count += 1
        for creg in circ.cregs:
            registers.append(creg)
            creg_order[f"circ{index}reg{creg.name}"] = creg_count
            creg_count += 1
        register_mapping = {}
        for reg in registers:
            reg_copy = copy.deepcopy(reg)
            reg_copy.name =  f"circ{index}reg{reg.name}"
            agg_circuit.add_register(reg_copy)
            register_mapping[reg_copy.name] = reg.name
        aggregate_info[job.id]["reg_mapping"] = register_mapping
        aggregate_info["reg_order"] = {"qreg":qreg_order, "creg":creg_order}
    
    qubit_count = 0
    clbit_count = 0

    for job in list_of_jobs:
        circ = job.circuit
        qubits = range(qubit_count, qubit_count + len(circ.qubits))
        clbits = range(clbit_count, clbit_count + len(circ.clbits))
        agg_circuit.compose(circ, qubits=qubits, clbits=clbits, inplace=True)
        qubit_count += len(circ.qubits)
        clbit_count += len(circ.clbits)
        aggregate_info[job.id]["qubits"] = {"start":qubits.start, "stop":qubits.stop}
        aggregate_info[job.id]["clbits"] = {"start":clbits.start, "stop":clbits.stop}
    agg_qc_obj = Quantum_Job(agg_circuit, Modification_Type.aggregation)
    agg_qc_obj.input_jobs.extend(list_of_jobs)
    agg_qc_obj.mod_info = aggregate_info
    session.add(agg_qc_obj)
    session.commit()
    return agg_qc_obj

def results(result: Result, job: Quantum_Job) -> List[Result]:
    results = []
    agg_info = job.mod_info
    for job_item in job.input_jobs:
        job_result = __calc_results(job_item, agg_info, result)
        results.append(Result(result.backend_name, result.backend_version, job_item.id, job_item.qiskit_job_id, result.success, job_result, result.date, result.status, result.header))
    return results

def __calc_results(job_item:Quantum_Job, agg_info:Dict ,result:Result) -> Result:
    print(agg_info)
    result_dict_copy = copy.deepcopy(result.to_dict())
    # print(result_dict_copy)
    return result

if __name__ == "__main__":
    
    circ1 = random_circuit(10, 10, measure=True)
    circ2 = random_circuit(10, 10, measure=True)
    
    qc_obj_1 = Quantum_Job(circ1)
    qc_obj_2 = Quantum_Job(circ2)

    agg = aggregate_q_jobs([qc_obj_1, qc_obj_2])


