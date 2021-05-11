import copy
from typing import Dict, Tuple
from quantum_execution_job import QuantumExecutionJob, Execution_Type
from queue import Queue
from threading import Thread
from resource_mapping.backend_chooser import Backend_Chooser, Backend_Data
import logger

class NoSuitableModification(Exception):
    pass

class QuantumResourceMapper(Thread):
    
    def __init__(self, input:Queue, output:Queue, output_agg:Queue, output_part:Queue, backend_chooser:Backend_Chooser, config:Dict=None, error_queue:Queue=None) -> None:
        self._log = logger.get_logger(type(self).__name__)
        self._input = input
        self._output = output
        self._output_agg = output_agg
        self._output_part = output_part
        self._backend_chooser = backend_chooser
        self._error_queue = error_queue
        self._config_dict = {
            "execution_types":{
                "raw":True,
                "aggregation":True,
                "partition":True
            },
            "optimization_goal":"high_throughput"
        }
        if not config is None:
            self._config_dict.update(config)
        Thread.__init__(self)
        self._log.info("Init QuantumResourceMapper")

    def decide_action(self, job:QuantumExecutionJob) -> Tuple[Execution_Type, Backend_Data]:
        config = copy.deepcopy(self._config_dict)
        if "quantum_resource_mapper" in job.config.keys():
            if "execution_types" in job.config["quantum_resource_mapper"].keys():
                config["execution_types"].update(job.config["quantum_resource_mapper"]["execution_types"])
            if "optimization_goal" in job.config["quantum_resource_mapper"].keys():
                config["optimization_goal"] = job.config["quantum_resource_mapper"]["optimization_goal"]
            
        mod_none = config["execution_types"]["raw"]
        mod_agg = config["execution_types"]["aggregation"]
        mod_part = config["execution_types"]["partition"]
        optimization_goal = config["optimization_goal"]
        n_qubits = job.circuit.num_qubits
        config_bc = None
        if "backend_chooser" in job.config["quantum_resource_mapper"].keys():
            config_bc = job.config["quantum_resource_mapper"]["backend_chooser"]
        if optimization_goal == "high_throughput":
            # aggregation > none > partition
            if mod_agg:
                backend_record = self._backend_chooser.get_least_busy(filter_dict=config_bc, filter_func=lambda x: x.n_qubits>=2*n_qubits)
                if backend_record:
                    backend_name, backend_data = backend_record
                    return Execution_Type.aggregation, backend_data
            if mod_none:
                backend_record = self._backend_chooser.get_least_busy(filter_dict=config_bc, filter_func=lambda x: x.n_qubits>=n_qubits)
                if backend_record:
                    backend_name, backend_data = backend_record
                    return Execution_Type.raw, backend_data
            if mod_part:
                for i in range(n_qubits, 0, -1):
                    backend_record = self._backend_chooser.get_least_busy(filter_dict=config_bc, filter_func=lambda x: x.n_qubits>=i)
                    if backend_record:
                        backend_name, backend_data = backend_record
                        return Execution_Type.partition, backend_data

        else:
            # least_busy: Use the backend which is least busy. If possible aggregate. If aggregation and none is not possible, try partition
            backend_record = self._backend_chooser.get_least_busy(filter_dict=config_bc, filter_func=lambda x: x.n_qubits>=n_qubits)
            if backend_record:
                backend_name, backend_data = backend_record
                if mod_agg and n_qubits <= backend_data.n_qubits/2:
                    return Execution_Type.aggregation, backend_data
                elif mod_none:
                    return Execution_Type.raw, backend_data
           
            # partition needed because there is no suitable backend
            if mod_part:
                for i in range(n_qubits, 0, -1):
                    backend_record = self._backend_chooser.get_least_busy(filter_dict=config_bc, filter_func=lambda x: x.n_qubits>=i)
                    if backend_record:
                        backend_name, backend_data = backend_record
                        return Execution_Type.partition, backend_data
        raise NoSuitableModification




    def run(self) -> None:
        self._log.info("Started QuantumResourceMapper")
        while True:
            job:QuantumExecutionJob = self._input.get()
            self._log.debug(f"Got job {job.id}")
            try:
                mod_type, backend_data = self.decide_action(job)
                job.backend_data = backend_data
                self._log.info(f"Mod.Type = {mod_type}, Backend = {backend_data.name}")
                if mod_type == Execution_Type.aggregation:
                    self._output_agg.put(job)
                elif mod_type == Execution_Type.partition:
                    self._output_part.put(job)
                else:
                    self._output.put(job)
            except NoSuitableModification:
                self._log.debug(f"No suitable modification type for job {job.id}")
                if self._error_queue is not None:
                    self._error_queue.put(job)
                
            
