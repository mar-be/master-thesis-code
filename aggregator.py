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
    aggregate_info["total_qubits"] = qubit_count
    aggregate_info["total_clbits"] = clbit_count
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
        results.append(job_result)
    return results

def __calc_results(job_item:Quantum_Job, agg_info:Dict ,result:Result) -> Result:
    result_dict = result.to_dict()
    result_dict_copy = copy.deepcopy(result_dict)
    qubits_start = agg_info[str(job_item.id)]["qubits"]["start"]
    qubits_stop = agg_info[str(job_item.id)]["qubits"]["stop"]
    n_qubits = qubits_stop - qubits_start
    circ_size = agg_info["total_qubits"]
    reg_mapping = agg_info[str(job_item.id)]["reg_mapping"]
    data = result.data()["counts"]
    print(data)
    counts = {}
    for qubit_state in range(0, 2**n_qubits):
        count = 0
        for i in range(0, 2**(circ_size-n_qubits)):
            left_padding = i % (2**qubits_start)
            right_padding = i % (2**(circ_size-qubits_stop))
            state = left_padding + (qubit_state << qubits_start) + (right_padding << qubits_stop)
            hex_state = hex(state)
            if hex_state in data:
                count += data[hex_state]
        if count > 0:
            counts[hex(qubit_state)] = count
    print(counts)
                
    print(result_dict_copy)
    if len(result_dict["results"]) == 1:
        result_dict_copy["results"][0]["data"]["counts"] = counts
        header = result_dict["results"][0]["header"]
    else:
        raise Exception("Result length not 1")

    clbit_labels = __relabel(reg_mapping, header, "clbit_labels")
    qubit_labels = __relabel(reg_mapping, header, "qubit_labels")

    creg_sizes = __relabel(reg_mapping, header, "creg_sizes")
    qreg_sizes = __relabel(reg_mapping, header, "qreg_sizes")

    result_dict_copy["results"][0]["header"]["clbit_labels"] = clbit_labels
    result_dict_copy["results"][0]["header"]["creg_sizes"] = creg_sizes

    if len(qubit_labels) > 0:
        result_dict_copy["results"][0]["header"]["qubit_labels"] = qubit_labels
    
    if len(qreg_sizes) > 0:
        result_dict_copy["results"][0]["header"]["qreg_sizes"] = qreg_sizes
        result_dict_copy["results"][0]["header"]["n_qubits"] = n_qubits

    return Result.from_dict(result_dict_copy)

def __relabel(reg_mapping, header, key):
    labels = []
    for label in header[key]:
        if label[0] in reg_mapping:
            labels.append([reg_mapping[label[0]], label[1]])
    return labels

if __name__ == "__main__":
    
    circ1 = random_circuit(10, 10, measure=True)
    circ2 = random_circuit(10, 10, measure=True)
    
    qc_obj_1 = Quantum_Job(circ1)
    qc_obj_2 = Quantum_Job(circ2)

    agg = aggregate_q_jobs([qc_obj_1, qc_obj_2])


