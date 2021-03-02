from queue import Queue
from threading import Thread
from typing import Dict, List

from qiskit.circuit.quantumcircuit import QuantumCircuit
from cutqc.cutter import find_cuts
from cutqc.helper_fun import check_valid
from cutqc.evaluator import generate_subcircuit_instances

from qiskit_helper_functions.non_ibmq_functions import apply_measurement

from quantum_job import Modification_Type, QuantumJob

import logger


class Partitioner(Thread):

    def __init__(self, input:Queue, output:Queue, partition_dict:Dict, num_subcircuits:List[int], max_cuts:int) -> None:
        self._log = logger.get_logger(type(self).__name__)
        self._input = input
        self._output = output
        self._partition_dict = partition_dict
        self._num_subcircuits = num_subcircuits
        self._max_cuts = max_cuts
        Thread.__init__(self)

    def run(self) -> None:
        while True:
            job = self._input.get()
            try:
                self._log.info(f"Searching for cut for job {job.id}")
                sub_jobs = self._cut_job(job)
                self._log.info(f"Found cut for job {job.id}")
                for sub_job in sub_jobs:
                    self._output.put(sub_job)
            except Exception as e:
                self._log.exception(e)

    def _cut(self, circuit:QuantumCircuit, max_subcircuit_qubit):
        assert(check_valid(circuit=circuit))
        self._log.debug('*'*20+'Cut'+'*'*20)
        cut_solution = find_cuts(circuit, max_subcircuit_qubit, self._num_subcircuits, self._max_cuts, self._log.level==logger.logging.DEBUG)
        self._log.debug('*'*20+'Generate Subcircuits'+'*'*20)
        circ_dict, all_indexed_combinations = generate_subcircuit_instances(subcircuits=cut_solution["subcircuits"], complete_path_map=cut_solution["complete_path_map"])
        return cut_solution, circ_dict, all_indexed_combinations

    def _cut_job(self, qJob:QuantumJob):
        cut_solution, circ_dict, all_indexed_combinations = self._cut(qJob.circuit.remove_final_measurements(inplace=False), qJob.backend_data.n_qubits)
        sub_jobs = []
        for key, circ_info in circ_dict.items():
            circ = circ_info["circuit"]
            shots = circ_info["shots"]
            qc=apply_measurement(circuit=circ,qubits=circ.qubits)
            sub_jobs.append(QuantumJob(qc, type=Modification_Type.partition, parent=qJob.id, shots=qJob.shots, key=key, backend_data=qJob.backend_data))
        self._partition_dict[qJob.id] = {"cut_solution":cut_solution, "all_indexed_combinations":all_indexed_combinations, "job":qJob, "num_sub_jobs":len(sub_jobs)}
        return sub_jobs
