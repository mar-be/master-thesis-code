from typing import Tuple
from qiskit.providers.backend import Backend
from quantum_job import QuantumJob, Modification_Type
from queue import Queue
from threading import Thread
from analyzer.backend_chooser import Backend_Chooser, no_simulator_filter
import logger

class CircuitAnalyzer(Thread):
    
    def __init__(self, input:Queue, output:Queue, output_agg:Queue, output_part:Queue, backend_chooser:Backend_Chooser) -> None:
        self._log = logger.get_logger(type(self).__name__)
        self._input = input
        self._output = output
        self._output_agg = output_agg
        self._output_part = output_part
        self._backend_chooser = backend_chooser
        Thread.__init__(self)
        self._log.info("Init CircuitAnalyzer")

    def decide_action(self, job:QuantumJob) -> Tuple[Modification_Type, Backend]:
        n_qubits = job.circuit.num_qubits
        backend_record = self._backend_chooser.get_least_busy(filters=lambda x: x["n_qubits"]>=n_qubits and no_simulator_filter(x))
        if backend_record:
            backend_name, backend_dict = backend_record
            backend = backend_dict["backend"]
            if n_qubits <= backend.configuration().n_qubits/2:
                return Modification_Type.aggregation, backend
            else:
                return Modification_Type.none, backend
        # partition needed because there is no suitable backend 
        while backend_record == None:
            n_qubits -= 1
            backend_record = self._backend_chooser.get_least_busy(filters=lambda x: x["n_qubits"]>=n_qubits and no_simulator_filter(x))
        backend_name, backend_dict = backend_record
        backend = backend_dict["backend"]
        return Modification_Type.partition, backend




    def run(self) -> None:
        self._log.info("Started CircuitAnalyzer")
        while True:
            job:QuantumJob = self._input.get()
            self._log.debug(f"Got job {job.id}")
            mod_type, backend = self.decide_action(job)
            self._log.info(f"Mod.Type = {mod_type}, Backend = {backend.name()}")
            if mod_type == Modification_Type.none:
                pass
            elif mod_type == Modification_Type.aggregation:
                pass
            else:
                pass
