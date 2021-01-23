import copy
from typing import Dict, List, Any, Tuple
from qiskit import QuantumCircuit
from qiskit.circuit import register
from qiskit.circuit.random import random_circuit
from qiskit.result import Result
from qiskit.result.counts import Counts
from quantum_ciruit_object import Modification_Type, Quantum_Job, session


def aggregate_q_jobs(list_of_circuits: List[QuantumCircuit]) -> Tuple[QuantumCircuit, Dict[Any, Any]]:
    agg_circuit = QuantumCircuit()
    agg_info = {}
    qreg_count = 0
    creg_count = 0
    qreg_order = {}
    creg_order = {}
    circ_info = {}
    for index, circ in enumerate(list_of_circuits):
        circ_info[index] = {}
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
        circ_info[index]["reg_mapping"] = register_mapping
    agg_info["reg_order"] = {"qreg":qreg_order, "creg":creg_order}
    
    qubit_count = 0
    clbit_count = 0

    for index, circ in enumerate(list_of_circuits):
        qubits = range(qubit_count, qubit_count + len(circ.qubits))
        clbits = range(clbit_count, clbit_count + len(circ.clbits))
        agg_circuit.compose(circ, qubits=qubits, clbits=clbits, inplace=True)
        qubit_count += len(circ.qubits)
        clbit_count += len(circ.clbits)
        circ_info[index]["qubits"] = {"start":qubits.start, "stop":qubits.stop}
        circ_info[index]["clbits"] = {"start":clbits.start, "stop":clbits.stop}
    agg_info["circuits"] = circ_info
    agg_info["total_qubits"] = qubit_count
    agg_info["total_clbits"] = clbit_count
    return agg_circuit, agg_info

def split_results(result: Result, agg_info:Dict[Any, Any]) -> List[Result]:
    results = []
    for index in agg_info["circuits"]:
        job_result = __calc_result(index, agg_info, result)
        results.append(job_result)
    return results

def __calc_result(index:int, agg_info:Dict[Any, Any], result:Result) -> Result:
    result_dict = result.to_dict()
    result_dict_copy = copy.deepcopy(result_dict)
    qubits_start = agg_info["circuits"][index]["qubits"]["start"]
    qubits_stop = agg_info["circuits"][index]["qubits"]["stop"]
    n_qubits = qubits_stop - qubits_start
    circ_size = agg_info["total_qubits"]
    reg_mapping = agg_info["circuits"][index]["reg_mapping"]
    data = result.data()["counts"]
    counts = {}
    bit_mask = sum([2**i for i in range(n_qubits)])
    for state in data:
        state_int = int(state, 16)
        state_int = state_int >> qubits_start
        state_int = state_int & bit_mask
        state_hex = hex(state_int)
        count = data[state]
        if state_hex in counts:
            counts[state_hex] += count
        else:
            counts[state_hex] = count

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
    result_dict_copy["results"][0]["header"]["memory_slots"] = n_qubits

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

    agg, agg_info = aggregate_q_jobs([circ1, circ2])

    print(agg)

    print(agg_info)

