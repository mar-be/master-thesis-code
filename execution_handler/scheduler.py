import copy
import math
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from time import sleep
from typing import Any, Dict, Optional

import logger
from qiskit import IBMQ, QuantumCircuit, assemble, execute, transpile
from qiskit.compiler import assemble
from qiskit.providers import Job
from qiskit.providers.basebackend import BaseBackend
from qiskit.result.models import ExperimentResultData
from qiskit.result.result import Result

class AbstractExecution():

    def __init__(self) -> None:
        self._log = logger.get_logger(type(self).__name__)


    def _add_dicts(self, d1, d2):
        c = Counter(d1)
        c.update(d2)
        return dict(c)

    def _process_job_result(self, job_result, schedule_item, index, previous_key, previous_memory, previous_counts):
        results = {}
        exp_number = 0
        # get the Result as dict and delete the results 
        result_dict = job_result.to_dict()
        
        self._log.info(f"Process result of job {index}")

        for exp in schedule_item.experiments:
            key = exp["key"]
            circ = exp["circuit"]
            reps = exp["reps"]
            shots = exp["shots"]
            total_shots = exp["total_shots"]
            memory = []
            counts = {}
            result_data = None

            

            if previous_memory:
                # there is data from the previous job
                assert(previous_key==key)
                memory.extend(previous_memory)
                counts.update(previous_counts)
                shots += len(previous_memory)
                total_shots += len(previous_memory)
                previous_memory = None
                previous_counts = None
                previous_key = None
            
            # get ExperimentResult as dict
            job_exp_result_dict = job_result._get_experiment(exp_number).to_dict() 

            if not (shots == total_shots and reps == 1 and len(memory) == 0):
                # do not run this block if it is only one experiment (shots == total_shots) with one repetition and no previous data is available
                for exp_index in range(exp_number, exp_number+reps):
                    mem = job_result.data(exp_index)['memory']
                    memory.extend(mem)
                    cnts = job_result.data(exp_index)['counts']
                    
                    if exp_index == exp_number+reps-1 and shots == total_shots:
                        # last experiment for this circuit
                        if len(memory) > total_shots:
                            # trim memory and counts w.r.t. number of shots
                            too_much = len(memory) - total_shots
                            memory = memory[:total_shots]
                            mem = mem[:-too_much]
                            cnts = dict(Counter(mem))

                    counts = self._add_dicts(counts, cnts)
                
                if shots < total_shots:
                    previous_memory = copy.deepcopy(memory)
                    previous_counts = copy.deepcopy(counts)
                    previous_key = key
                    continue
                
                result_data = ExperimentResultData(counts=counts, memory=memory).to_dict()

                # overwrite the data and the shots
                job_exp_result_dict["data"] = result_data
                job_exp_result_dict["shots"] = total_shots

            # overwrite the results with the computed result
            result_dict["results"] = [job_exp_result_dict]
            results[key] = Result.from_dict(result_dict)
            exp_number += reps
        return results, previous_key, previous_memory, previous_counts


class ScheduleItem():
    '''A schedule item represents a job on a backend. It can contain multiple experiments.'''

    def __init__(self, max_shots: int, max_experiments: int):
        self._log = logger.get_logger(type(self).__name__)
        self.max_shots = max_shots
        self.shots = 0
        self.max_experiments = max_experiments
        self.experiments = []
        self.remaining_experiments = max_experiments
        self.n_circuits = 0

    
    def add_circuit(self, key, circuit:QuantumCircuit, shots:int) -> int:
        """Add a circuit to the ScheduleItem.

        Args:
            key (Any): Identifier for the circuit
            circuit (QuantumCircuit): The circuit, which should be executed
            shots (int): The number of shots
    
        Returns:
            int: remaining shots. If they are 0, all shots are executed
        """
        if self.remaining_experiments == 0:
            return shots

        self.n_circuits += 1
        reps = math.ceil(shots/self.max_shots)
        self.shots = max(self.shots, min(shots, self.max_shots))

        if reps <= self.remaining_experiments:
            remaining_shots = 0
        else:
            reps = self.remaining_experiments
            remaining_shots = shots - reps*self.max_shots

        self.remaining_experiments -= reps
        self.experiments.append({"key":key, "circuit":circuit, "reps":reps, "shots":shots-remaining_shots, "total_shots":shots})
        
        return remaining_shots

class BackendControl():
    """Control the access to the backend to regulate the number jobs, which are executed in parallel"""

    def __init__(self, backend):
        self._log = logger.get_logger(type(self).__name__)
        self._backend = backend
        self._lock = Lock()
        self._counter = 0
        
    def try_to_enter(self):
        with self._lock:
            limit = self._backend.job_limit()
            self._log.debug(f"Counter:{self._counter} Active_Jobs:{limit.active_jobs} Maximum_jobs:{limit.maximum_jobs}")
            if limit.active_jobs < limit.maximum_jobs:
                if self._counter < limit.maximum_jobs:
                    self._counter += 1
                    return True
            return False

    def leave(self):
        with self._lock:
            self._counter -= 1
    
class Scheduler(AbstractExecution):

    def __init__(self, circuits:dict, backend:BaseBackend, max_shots:Optional[int]=None, max_experiments:Optional[int]=None):
        self._log = logger.get_logger(type(self).__name__)
        self._circuits = circuits
        self._backend = backend
        self._control = BackendControl(self._backend) 
        if max_shots != None:
            self._max_shots = max_shots
        else:
            self._max_shots = backend.configuration().max_shots
        if max_experiments != None:
            self._max_experiments = max_experiments
        else:
            self._max_experiments = backend.configuration().max_experiments
        self._schedule = []
        self._jobs = []
        self._generate_schedule()

    def _generate_schedule(self):
        """Generate a schedule constisting of ScheduleItems"""
        if len(self._circuits) == 0:
            return
        schedule_item = ScheduleItem(self._max_shots, self._max_experiments)
        self._schedule.append(schedule_item)
        for key, item in self._circuits.items():
            circuit = item["circuit"]
            shots = item["shots"]
            remaining_shots = schedule_item.add_circuit(key, circuit, shots)
            while remaining_shots > 0:
                schedule_item = ScheduleItem(self._max_shots, self._max_experiments)
                self._schedule.append(schedule_item)
                remaining_shots = schedule_item.add_circuit(key, circuit, remaining_shots)
        self._log.info(f"Schedule has {len(self._schedule)} items")


    def _submit_future_function(self, item: ScheduleItem, index:Optional[int]=None) -> Job:
        circuits_to_execute = []
        for circuit_item in item.experiments:
            circ = circuit_item["circuit"]
            reps = circuit_item["reps"]
            circuits_to_execute.extend([circ]*reps)
        # job = execute(circuits_to_execute, self.backend, shots=item.shots, memory=True)
        qobj = assemble(transpile(circuits_to_execute, backend=self._backend), self._backend, shots=item.shots, memory=True)
        while not self._control.try_to_enter():
            sleep(1)
        job = self._backend.run(qobj)
        if index != None:
            self._log.info(f"Job {index} is submitted to the backend")
        # use this to wait till the job is finished
        job.result()
        self._control.leave()
        if index != None:
            self._log.info(f"Results for job {index} are available")
        return job

    def submit_jobs(self):
        """Submit the circuits to the backend to execute them."""
        if len(self._jobs) > 0:
            raise Exception("Jobs are allready submitted")
        self._log.info("Start submitting jobs")
        n_workers = min(len(self._schedule), self._backend.job_limit().maximum_jobs)
        executor =  ThreadPoolExecutor(n_workers)
        for index, item in enumerate(self._schedule):
            future = executor.submit(self._submit_future_function, item, index)
            self._jobs.append(future)
                
    


    def get_results(self) -> Dict[Any, Result]:
        """Get the results for the submited jobs.

        Returns: 
            dict : A dictionary containing a mapping from keys to results
        """

        assert(len(self._jobs)==len(self._schedule))
        previous_key = None
        previous_memory = None
        previous_counts = None
        

        results = {}
        self._log.info("Wait for results")
        for index, schedule_item in enumerate(self._schedule):
            job = self._jobs[index].result()
            job_result = job.result()

            result_for_item, previous_key, previous_memory, previous_counts = self._process_job_result(job_result, schedule_item, index, previous_key, previous_memory, previous_counts)
            results.update(result_for_item)
            
        
        self._log.info("All results are processed")
        return results

    

                    
        


    
if __name__ == "__main__":

    provider = IBMQ.load_account()

    backend = provider.get_backend('ibmq_athens')

    backend_sim = provider.get_backend('ibmq_qasm_simulator')

    from qiskit.circuit.random import random_circuit


    circs = {i:{"circuit":random_circuit(5, 5 , measure=True), "shots":10000} for i in range(900)}

    scheduler = Scheduler(circs, backend_sim)
    scheduler.submit_jobs()
    res = scheduler.get_results()
    for i in range(len(circs)):
        c = circs[i]["circuit"]
        r = res[i]
        print(i, r.get_counts(c))
