import copy

from typing import Dict, List, Any, Tuple
from queue import Empty, Queue
from threading import Thread

from qiskit import QuantumCircuit, circuit
from qiskit.circuit.random import random_circuit
from qiskit.result import Result

from quantum_job import QuantumJob, Modification_Type


import logger



class Aggregator(Thread):

    def __init__(self, input, output:Queue, job_dict:Dict, timeout: float) -> None:
        self._log = logger.get_logger(type(self).__name__)
        self._input:Queue = input
        self._output:Queue = output
        self._job_dict:Dict = job_dict
        self._timeout:float = timeout
        Thread.__init__(self)
        self._log.info("Init Aggregator")

    
    def run(self) -> None:
        self._log.info("Started Aggregator")
        jobs_to_aggregate = []
        while True:
            try:
                q_job = self._input.get(timeout=self._timeout)
                jobs_to_aggregate.append(q_job)
            except Empty:
                if len(jobs_to_aggregate) == 0:
                    continue
                elif len(jobs_to_aggregate) == 1:
                    self._output.put(jobs_to_aggregate.pop())
            if len(jobs_to_aggregate) < 2:
                continue
            agg_circ, agg_info = aggregate([job.circuit for job in jobs_to_aggregate])
            agg_shots = max([job.shots for job in jobs_to_aggregate])
            agg_job = QuantumJob(agg_circ, Modification_Type.aggregation, shots = agg_shots)
            self._job_dict[agg_job.id] = {"jobs":copy.deepcopy(jobs_to_aggregate), "agg_info":agg_info}
            self._output.put(agg_job)
            jobs_to_aggregate = []

class AggregatorResults(Thread):
    
    def __init__(self, input, output:Queue, job_dict:Dict):
        self._log = logger.get_logger(type(self).__name__)
        self._input:Queue = input
        self._output:Queue = output
        self._job_dict:Dict = job_dict
        Thread.__init__(self)
        self._log.info("Init AggregatorResults")

    def run(self) -> None:
        self._log.info("Started AggregatorResults")
        while True:
            agg_job = self._input.get()
            try:
                job_info = self._job_dict.pop(agg_job.id)
            except KeyError as k_e:
                # TODO exception handling
                raise k_e
            results = split_results(agg_job.result, job_info["agg_info"])
            initial_jobs = job_info["jobs"]
            assert(len(results)==len(initial_jobs))
            for i, job in enumerate(initial_jobs):
                job.result = results[i]
                self._output.put(job)
            



def aggregate(list_of_circuits: List[QuantumCircuit]) -> Tuple[QuantumCircuit, Dict[Any, Any]]:
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

    agg, agg_info = aggregate([circ1, circ2])

    print(agg)

    print(agg_info)


