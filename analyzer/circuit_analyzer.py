from logging import error
from typing import Dict, Tuple
from qiskit.providers.backend import Backend
from quantum_job import QuantumJob, Modification_Type
from queue import Queue
from threading import Thread
from analyzer.backend_chooser import Backend_Chooser, Backend_Data
import logger

class NoSuitableModification(Exception):
    pass

class CircuitAnalyzer(Thread):
    
    def __init__(self, input:Queue, output:Queue, output_agg:Queue, output_part:Queue, backend_chooser:Backend_Chooser, config:Dict=None, error_queue:Queue=None) -> None:
        self._log = logger.get_logger(type(self).__name__)
        self._input = input
        self._output = output
        self._output_agg = output_agg
        self._output_part = output_part
        self._backend_chooser = backend_chooser
        self._error_queue = error_queue
        self._optimization_goal = "least_busy"
        self._mod_none = True
        self._mod_agg = True
        self._mod_part = True
        if not config is None:
            try:
                self._mod_none = config["modification_types"]["none"]
            except KeyError:
                pass
            try:
                self._mod_agg = config["modification_types"]["aggregation"]
            except KeyError:
                pass
            try:
                self._mod_part = config["modification_types"]["partition"]
            except KeyError:
                pass
            try:
                self._optimization_goal = config["optimization_goal"]
            except KeyError:
                pass


        Thread.__init__(self)
        self._log.info("Init CircuitAnalyzer")

    def decide_action(self, job:QuantumJob) -> Tuple[Modification_Type, Backend_Data]:
        mod_none = self._mod_none
        mod_agg = self._mod_agg
        mod_part = self._mod_part
        n_qubits = job.circuit.num_qubits
        if self._optimization_goal == "efficient_qubit_usage":
            # aggregation > none > partition
            if mod_agg:
                backend_record = self._backend_chooser.get_least_busy(filter_func=lambda x: x.n_qubits>=2*n_qubits)
                if backend_record:
                    backend_name, backend_data = backend_record
                    return Modification_Type.aggregation, backend_data
            if mod_none:
                backend_record = self._backend_chooser.get_least_busy(filter_func=lambda x: x.n_qubits>=n_qubits)
                if backend_record:
                    backend_name, backend_data = backend_record
                    return Modification_Type.none, backend_data
            if mod_part:
                for i in range(n_qubits, 0, -1):
                    backend_record = self._backend_chooser.get_least_busy(filter_func=lambda x: x.n_qubits>=i)
                    if backend_record:
                        backend_name, backend_data = backend_record
                        return Modification_Type.partition, backend_data

        else:
            # least_busy: Use the backend which is least busy. If possible aggregate. If aggregation and none is not possible, try partition
            backend_record = self._backend_chooser.get_least_busy(filter_func=lambda x: x.n_qubits>=n_qubits)
            if backend_record:
                backend_name, backend_data = backend_record
                if mod_agg and n_qubits <= backend_data.n_qubits/2:
                    return Modification_Type.aggregation, backend_data
                elif mod_none:
                    return Modification_Type.none, backend_data
           
            # partition needed because there is no suitable backend
            if mod_part:
                for i in range(n_qubits, 0, -1):
                    backend_record = self._backend_chooser.get_least_busy(filter_func=lambda x: x.n_qubits>=i)
                    if backend_record:
                        backend_name, backend_data = backend_record
                        return Modification_Type.partition, backend_data
        raise NoSuitableModification




    def run(self) -> None:
        self._log.info("Started CircuitAnalyzer")
        while True:
            job:QuantumJob = self._input.get()
            self._log.debug(f"Got job {job.id}")
            try:
                mod_type, backend_data = self.decide_action(job)
                job.backend_data = backend_data
                self._log.info(f"Mod.Type = {mod_type}, Backend = {backend_data.name}")
                if mod_type == Modification_Type.aggregation:
                    self._output_agg.put(job)
                elif mod_type == Modification_Type.partition:
                    self._output_part.put(job)
                else:
                    self._output.put(job)
            except NoSuitableModification:
                self._log.debug(f"No suitable modification type for job {job.id}")
                if self._error_queue is not None:
                    self._error_queue.put(job)
                
            
