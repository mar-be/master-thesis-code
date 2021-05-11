from queue import Queue
from threading import Thread
from typing import Dict, List, Tuple

from qiskit.circuit.quantumcircuit import QuantumCircuit
from cutqc.cutter import find_cuts
from cutqc.helper_fun import check_valid
from cutqc.evaluator import generate_subcircuit_instances

from qiskit_helper_functions.non_ibmq_functions import apply_measurement

from quantum_job import Execution_Type, QuantumJob

import logger

class NoFeasibleCut(Exception):
    pass

class Partitioner(Thread):

    def __init__(self, input:Queue, output:Queue, partition_dict:Dict, max_separate_circuits:int, max_cuts:int, error_queue:Queue=None) -> None:
        self._log = logger.get_logger(type(self).__name__)
        self._input = input
        self._output = output
        self._partition_dict = partition_dict
        self._max_separate_circuits = max_separate_circuits
        self._max_cuts = max_cuts
        self._error_queue = error_queue
        Thread.__init__(self)

    def run(self) -> None:
        while True:
            job = None
            try:
                job = self._input.get()
                self._log.info(f"Searching for cut for job {job.id}")
                sub_jobs = self._cut_job(job)
                self._log.info(f"Found cut for job {job.id}: Generated {len(sub_jobs)} sub-jobs")
                for sub_job in sub_jobs:
                    self._output.put(sub_job)
            except (AssertionError, NoFeasibleCut) as e:
                self._log.debug(f"Job {job.id} not feasible for partition")
                if self._error_queue:
                    job.error = str(e)
                    self._error_queue.put(job)
                else:
                    self._log.exception(e)

    def _cut(self, circuit:QuantumCircuit, subcircuit_max_qubits, max_separate_circuits, max_cuts):
        assert(check_valid(circuit=circuit))
        self._log.debug('*'*20+'Cut'+'*'*20)
        cut_solution = find_cuts(circuit, subcircuit_max_qubits, range(2, max_separate_circuits+1), max_cuts, self._log.level==logger.logging.DEBUG)
        if len(cut_solution) == 0:
            raise NoFeasibleCut
        self._log.debug('*'*20+'Generate Subcircuits'+'*'*20)
        circ_dict, all_indexed_combinations = generate_subcircuit_instances(subcircuits=cut_solution["subcircuits"], complete_path_map=cut_solution["complete_path_map"])
        return cut_solution, circ_dict, all_indexed_combinations

    def _cut_job(self, qJob:QuantumJob):
        subcircuit_max_qubits, max_separate_circuits, max_cuts = self._get_cutting_parameters(qJob)
        cut_solution, circ_dict, all_indexed_combinations = self._cut(qJob.circuit.remove_final_measurements(inplace=False), subcircuit_max_qubits, max_separate_circuits, max_cuts)
        self._log.debug(f"Cut contains {len(circ_dict)} different sub-circuits")
        sub_jobs = []
        for key, circ_info in circ_dict.items():
            circ = circ_info["circuit"]
            shots = circ_info["shots"]
            qc=apply_measurement(circuit=circ,qubits=circ.qubits)
            sub_jobs.append(QuantumJob(qc, type=Execution_Type.partition, parent=qJob.id, shots=qJob.shots, key=key, backend_data=qJob.backend_data))
        self._partition_dict[qJob.id] = {"cut_solution":cut_solution, "all_indexed_combinations":all_indexed_combinations, "job":qJob, "num_sub_jobs":len(sub_jobs)}
        return sub_jobs

    def _get_cutting_parameters(self, qJob:QuantumJob) -> Tuple[int, int, int]:
      
        try:
            subcircuit_max_qubits = min(qJob.config["partitioner"]["subcircuit_max_qubits"], qJob.backend_data.n_qubits)
        except KeyError:
            subcircuit_max_qubits = qJob.backend_data.n_qubits
        try:
            max_separate_circuits = qJob.config["partitioner"]["max_separate_circuits"]
        except KeyError:
            max_separate_circuits = self._max_separate_circuits
        try:
            max_cuts = qJob.config["partitioner"]["max_cuts"]
        except KeyError:
            max_cuts = self._max_cuts

        return subcircuit_max_qubits, max_separate_circuits, max_cuts