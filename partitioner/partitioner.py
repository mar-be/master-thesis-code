from queue import Queue
from threading import Thread
from typing import Dict, List, Tuple

import logger
from cutqc.cutter import find_cuts
from cutqc.evaluator import generate_subcircuit_instances
from cutqc.helper_fun import check_valid
from qiskit.circuit.quantumcircuit import QuantumCircuit
from qiskit_helper_functions.non_ibmq_functions import apply_measurement
from quantum_execution_job import Execution_Type, QuantumExecutionJob


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

    def _cut(self, circuit:QuantumCircuit, subcircuit_max_qubits:int, max_separate_circuits:int, max_cuts:int) -> Tuple[Dict, Dict, Dict]:
        """Partitions a quantum circuit with the given parameters

        Args:
            circuit (QuantumCircuit)
            subcircuit_max_qubits (int): maximal qubits for the sub-circuits
            max_separate_circuits (int): maximal separate circuit parts
            max_cuts (int): maximal number of cuts

        Raises:
            NoFeasibleCut: There is no solution with the given parameters

        Returns:
            Tuple[Dict, Dict, Dict]: Returns three Dicts containing the cut solution, an sub-circuit index and all combinations 
        """
        assert(check_valid(circuit=circuit))
        self._log.debug('*'*20+'Cut'+'*'*20)
        cut_solution = find_cuts(circuit, subcircuit_max_qubits, range(2, max_separate_circuits+1), max_cuts, self._log.level==logger.logging.DEBUG)
        if len(cut_solution) == 0:
            raise NoFeasibleCut
        self._log.debug('*'*20+'Generate Subcircuits'+'*'*20)
        circ_dict, all_indexed_combinations = generate_subcircuit_instances(subcircuits=cut_solution["subcircuits"], complete_path_map=cut_solution["complete_path_map"])
        return cut_solution, circ_dict, all_indexed_combinations

    def _cut_job(self, qJob:QuantumExecutionJob) -> List[QuantumExecutionJob]:
        """Partitions the quantum circuit of a QuantumExecutionJob

        Args:
            qJob (QuantumExecutionJob): the job to partition

        Returns:
            List[QuantumExecutionJob]: List of QuantumExecutionJobs containing the sub-circuits that result from the partition
        """
        subcircuit_max_qubits, max_separate_circuits, max_cuts = self._get_cutting_parameters(qJob)
        cut_solution, circ_dict, all_indexed_combinations = self._cut(qJob.circuit.remove_final_measurements(inplace=False), subcircuit_max_qubits, max_separate_circuits, max_cuts)
        self._log.debug(f"Cut contains {len(circ_dict)} different sub-circuits")
        sub_jobs = []
        for key, circ_info in circ_dict.items():
            circ = circ_info["circuit"]
            shots = circ_info["shots"]
            qc=apply_measurement(circuit=circ,qubits=circ.qubits)
            sub_jobs.append(QuantumExecutionJob(qc, type=Execution_Type.partition, parent=qJob.id, shots=qJob.shots, key=key, backend_data=qJob.backend_data))
        self._partition_dict[qJob.id] = {"cut_solution":cut_solution, "all_indexed_combinations":all_indexed_combinations, "job":qJob, "num_sub_jobs":len(sub_jobs)}
        return sub_jobs

    def _get_cutting_parameters(self, qJob:QuantumExecutionJob) -> Tuple[int, int, int]:
        """Get the cutting parameters for the given QuantumExecutionJob

        Args:
            qJob (QuantumExecutionJob)

        Returns:
            Tuple[int, int, int]: Returns the maximal qubits for the sub-circuits, the maximal separate circuit parts and the maximal number of cuts
        """
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
