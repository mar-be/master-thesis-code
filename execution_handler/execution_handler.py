from collections import Counter
from concurrent.futures import Future
import copy
import math
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from queue import Empty, Queue
from threading import Lock, Thread
from typing import Callable, Dict, List, Optional, Tuple
from qiskit import qobj
from qiskit.providers.ibmq.accountprovider import AccountProvider
from qiskit.providers.job import Job

from qiskit.qobj import Qobj
from qiskit.result.models import ExperimentResultData
from qiskit.result.result import Result

import logger
from qiskit import assemble, transpile
from qiskit.providers import Backend
from qiskit.providers.basebackend import BaseBackend
from qiskit.providers.provider import Provider
from quantum_job import QuantumJob

from execution_handler.scheduler import (AbstractExecution,
                                         ScheduleItem)


class BackendControl():
    """Control the access to the backends to regulate the number of queued jobs"""

    def __init__(self,):
        self._log = logger.get_logger(type(self).__name__)
        self._locks = {}
        self._counters = {}
        
    def try_to_enter(self, backend_name, backend):
        try:
            lock = self._locks[backend_name]
            counter = self._counters[backend_name]
        except KeyError:
            lock = Lock()
            counter = 0
            self._locks[backend_name] = lock
            self._counters[backend_name] = counter

        with lock:
            limit = backend.job_limit()
            self._log.debug(f"Backend: {backend_name} Counter:{counter} Active_Jobs:{limit.active_jobs} Maximum_jobs:{limit.maximum_jobs}")
            if limit.active_jobs < limit.maximum_jobs:
                if counter < limit.maximum_jobs:
                    self._counters[backend_name] += 1
                    return True
            return False

    def leave(self, backend_name):
        with self._locks[backend_name]:
            self._counters[backend_name] -= 1

class ExecutionSorter(Thread):

    def __init__(self, input:Queue, new_backend:Queue):
        self._log = logger.get_logger(type(self).__name__)
        self._input = input
        self._new_backend = new_backend
        self._backend_queue_table = {}
        Thread.__init__(self)
        self._log.info("Init")

    
    def run(self) -> None:
        self._log.info("Started")
        while True:
            job:QuantumJob = self._input.get()
            backend = job.backend
            if not backend in self._backend_queue_table.keys():
                backend_queue = Queue()
                self._backend_queue_table[backend] = backend_queue
                self._new_backend.put((backend, backend_queue))
                self._log.debug(f"Created new queue for backend {backend}")
            # self._log.debug(f"Sorted job {job.id} for backend {backend}")
            self._backend_queue_table[backend].put(job)
          
                
                

class Batch(ScheduleItem):
    
    def __init__(self, backen_name:str, max_shots: int, max_experiments: int, batch_number:int):
        self.backend_name = backen_name
        self.batch_number = batch_number
        super().__init__(max_shots, max_experiments)

class Batcher(Thread):

    def __init__(self, output: Queue, new_backend:Queue, get_max_batch_size:Callable[[str], int], get_max_shots:Callable[[str], int], quantum_job_table:Dict, batch_timeout:int=30) -> None:
        self._log = logger.get_logger(type(self).__name__)
        self._output = output
        self._new_backend = new_backend
        self._batch_timeout = batch_timeout
        self._quantum_job_table = quantum_job_table
        self._backend_queue_table = {}
        self._get_max_batch_size = get_max_batch_size
        self._backend_max_batch_size = {}
        self._get_max_shots = get_max_shots
        self._backend_max_shots = {}
        self._queue_timers = {}
        self._batch_count = 0
        Thread.__init__(self)
        self._log.info("Init")

    def _create_batches(self, backend_name:str, circuits:List[QuantumJob]):
        """Generate a list of batches"""
        if len(circuits) == 0:
            return
        batch = Batch(backend_name, self._backend_max_shots[backend_name], self._backend_max_batch_size[backend_name], self._batch_count)
        for job in circuits:
            key = job.id
            circuit = job.circuit
            shots = job.shots
            remaining_shots = batch.add_circuit(key, circuit, shots)
            while remaining_shots > 0:
                self._log.info(f"Generated batch {self._batch_count} for backend {backend_name}")
                self._output.put(batch)
                self._batch_count += 1
                batch = Batch(backend_name, self._backend_max_shots[backend_name], self._backend_max_batch_size[backend_name], self._batch_count)
                remaining_shots = batch.add_circuit(key, circuit, remaining_shots)
        self._log.info(f"Generated batch {self._batch_count} for backend {backend_name}")
        self._output.put(batch)
        self._batch_count += 1
        self._log.info(f"Added all circuits to batches for backend {backend_name}")

    def run(self) -> None:
        self._log.info("Started")
        while True:
            while not self._new_backend.empty():
                backend_name, backend_queue = self._new_backend.get()
                self._backend_queue_table[backend_name] = backend_queue
                self._backend_max_batch_size[backend_name] = self._get_max_batch_size(backend_name)
                self._backend_max_shots[backend_name] = self._get_max_shots(backend_name)
                self._log.debug(f"Got new backend {backend_name} with max batch size {self._backend_max_batch_size[backend_name]} and max shots {self._backend_max_shots[backend_name]}")

            for backend_name, backend_queue in self._backend_queue_table.items():
                if backend_queue.empty():
                    # nothimg to do since queue is empty
                    continue

                if not backend_name in self._queue_timers.keys():
                    # No timer is started but queue is not empty -> start a timer
                    self._queue_timers[backend_name] = time.time()
                
                if time.time() - self._queue_timers[backend_name] > self._batch_timeout or  backend_queue.qsize() >= self._backend_max_batch_size[backend_name]:
                    # Timeout occured or enough items for a wole batch -> try to get a batch
                    add_to_batch = []
                    for _ in range(self._backend_max_batch_size[backend_name]):
                        try:
                            job = backend_queue.get(block=False)
                            add_to_batch.append(job)
                            self._quantum_job_table[job.id] = job
                        except Empty:
                            break
                    self._create_batches(backend_name, add_to_batch)
                    if backend_queue.empty():
                        # delete timer because the queue is empty
                        self._queue_timers.pop(backend_name)
                    else:
                        # start a new timer
                        self._queue_timers[backend_name] = time.time()

class AbstractBackendInteractor(Thread):

    def __init__(self, input:Queue, output:Queue, provider:Provider):
            self._log = logger.get_logger(type(self).__name__)
            self._input = input
            self._output = output
            self._provider = provider
            self._backend_table = {}
            Thread.__init__(self)
            self._log.info("Init")

    def _get_backend(self, backend_name:str) -> Backend:
            try:
                return self._backend_table[backend_name]
            except KeyError:
                backend = self._provider.get_backend(backend_name)
                self._backend_table[backend_name] = backend
                return backend

class Assembler(AbstractBackendInteractor):

    def __init__(self, input: Queue, output: Queue, provider: Provider):
        super().__init__(input, output, provider)
        n_workers = 4
        self._executor =  ThreadPoolExecutor(n_workers)

    def _assemble(self, batch:Batch) -> Qobj:
        backend_name = batch.backend_name
        backend = self._get_backend(backend_name)
        circuits_to_execute = []
        for circuit_item in batch.experiments:
            circ = circuit_item["circuit"]
            reps = circuit_item["reps"]
            circuits_to_execute.extend([circ]*reps)
        qobj =  assemble(transpile(circuits_to_execute, backend=backend), backend, shots=batch.shots, memory=True)
        self._log.info(f"Assembled Qobj for batch {batch.batch_number}")
        return qobj

    def run(self) -> None:
        self._log.info("Started")
        while True:
            batch:Batch = self._input.get()
            self._log.info(f"Got batch {batch.batch_number} for backend {batch.backend_name}")
            future_qobj = self._executor.submit(self._assemble, batch)
            self._output.put((batch, future_qobj))
           



class Submitter(AbstractBackendInteractor):

    def __init__(self, input: Queue, output: Queue, provider: Provider, backend_control:BackendControl, defer_interval=60):
        self._backend_control = backend_control
        self._defer_interval = defer_interval
        self._internal_jobs_queue = []
        super().__init__(input, output, provider)

    def _submit(self, backend_name, qobj:Qobj) -> Job:
        backend = self._get_backend(backend_name)
        return backend.run(qobj)
        
    def run(self) -> None:
        self._log.info("Started")
        batch: Batch
        qobj: Qobj
        while True:
            try:
                self._internal_jobs_queue.append(self._input.get(timeout=self._defer_interval))
            except Empty:
                pass
            deferred_jobs = []
            for batch, qobj in self._internal_jobs_queue:
                if isinstance(qobj, Future):
                    if qobj.done():
                        qobj = qobj.result()
                    else:
                        self._log.debug(f"Qobj is not yet available -> defer job for batch {batch.batch_number}")
                        deferred_jobs.append((batch, qobj))
                        continue
                backend_name = batch.backend_name
                backend = self._get_backend(backend_name)
                if self._backend_control.try_to_enter(backend_name, backend):
                    job = self._submit(batch.backend_name, qobj)
                    self._log.info(f"Submitted batch {batch.batch_number} to {batch.backend_name}")
                    self._output.put((batch, job))
                else:
                    self._log.debug(f"Reached limit of queued jobs for backend {backend_name} -> defer job for batch {batch.batch_number}")
                    deferred_jobs.append((batch, qobj))
            self._internal_jobs_queue = deferred_jobs

            
class Retriever(Thread):

    def __init__(self, input: Queue, output: Queue, wait_time:float, backend_control:BackendControl):
        self._log = logger.get_logger(type(self).__name__)
        self._input = input
        self._output = output
        self._wait_time = wait_time
        self._backend_control = backend_control
        self._jobs = []   
        Thread.__init__(self)
        self._log.info("Init")    


    def run(self):
        self._log.info("Started")
        batch: Batch
        job: Job
        while True:
            i = 0
            while not self._input.empty() and i < 5:
                job_tuple = self._input.get()
                self._jobs.append(job_tuple)
                i += 1
            final_state_jobs = []
            for batch, job in self._jobs:
                if job.in_final_state():
                    final_state_jobs.append((batch, job))
                    self._backend_control.leave(batch.backend_name)
            for job_tuple in final_state_jobs:
                self._jobs.remove(job_tuple)
                self._output.put(job_tuple)
            time.sleep(self._wait_time)




    

class ResultProcessor(AbstractBackendInteractor):

    def __init__(self, input: Queue, output: Queue, provider: Provider, quantum_job_table:Dict):
        super().__init__(input, output, provider)
        self._quantum_job_table = quantum_job_table
        self._previous_key = {}
        self._previous_memory = {}
        self._previous_counts = {}

    def _add_dicts(self, d1, d2):
        c = Counter(d1)
        c.update(d2)
        return dict(c)

    def _process_job_result(self, job_result:Result, batch:Batch):
        results = {}
        exp_number = 0
        # get the Result as dict and delete the results 
        result_dict = job_result.to_dict()

        index = batch.batch_number
        backend_name = batch.backend_name
        try:
            previous_key = self._previous_key[backend_name]
            previous_memory = self._previous_memory[backend_name]
            previous_counts = self._previous_counts[backend_name]
        except KeyError:
            previous_key = None
            previous_memory = None
            previous_counts = None
        
        self._log.info(f"Process result of job {index}")

        for exp in batch.experiments:
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
        self._previous_key[backend_name] = previous_key
        self._previous_memory[backend_name] = previous_memory
        self._previous_counts[backend_name] = previous_counts
        return results

    def run(self) -> None:
        self._log.info("Started")
        batch: Batch
        job: Job
        while True:
            batch, job = self._input.get()
            job_result = job.result()
            self._log.info(f"Got result for batch {batch.batch_number} from {batch.backend_name}")
            result_for_batch = self._process_job_result(job_result, batch)
            for key, result in result_for_batch.items():
                try:
                    qjob = self._quantum_job_table.pop(key)
                    qjob.result = result
                    self._output.put(qjob)
                except KeyError as ke:
                    # TODO Exception Handling
                    raise ke

    

class ExecutionHandler():
    
    def __init__(self, provider:AccountProvider, input:Queue, output:Queue, batch_timeout:int = 30, retrieve_time:int = 30) -> None:
        new_backends = Queue()
        batcher_assembler = Queue()
        assembler_submitter = Queue()
        submitter_retrieber = Queue()
        retriever_processor = Queue()
        quantum_job_table = {}
        get_max_batch_size = lambda backend_name: provider.get_backend(backend_name).configuration().max_experiments
        get_max_shots = lambda backend_name: provider.get_backend(backend_name).configuration().max_shots
        backend_control = BackendControl()
        self._execution_sorter = ExecutionSorter(input, new_backends)
        self._batcher = Batcher(batcher_assembler, new_backends, get_max_batch_size, get_max_shots, quantum_job_table, batch_timeout)
        self._assembler = Assembler(input=batcher_assembler, output=assembler_submitter, provider=provider)
        self._submitter = Submitter(input=assembler_submitter, output=submitter_retrieber, provider=provider, backend_control=backend_control)
        self._retriever = Retriever(input=submitter_retrieber, output=retriever_processor, wait_time=retrieve_time, backend_control=backend_control)
        self._processor = ResultProcessor(input=retriever_processor, output=output, provider=provider, quantum_job_table=quantum_job_table)
    
    def start(self):
        self._execution_sorter.start()
        self._batcher.start()
        self._assembler.start()
        self._submitter.start()
        self._retriever.start()
        self._processor.start()

class ExecutionHandlerOld(AbstractExecution):

    def __init__(self, backend:BaseBackend, input:Queue, results:Queue, batch_timeout:int=30, max_shots:Optional[int]=None, max_experiments:Optional[int]=None):
        self._log = logger.get_logger(type(self).__name__)
        self._backend = backend
        self._control = BackendControl(self._backend) 
        self._input = input
        self._results = results
        self._batch_timeout = batch_timeout
        if max_shots != None:
            self._max_shots = max_shots
        else:
            self._max_shots = backend.configuration().max_shots
        if max_experiments != None:
            self._max_experiments = max_experiments
        else:
            self._max_experiments = backend.configuration().max_experiments
        self._max_jobs = backend.job_limit().maximum_jobs
        self._schedule = Queue(self._max_jobs)
        self._jobs = Queue(self._max_jobs)
        self._schedule_item_count = 0
        self._quantum_job_table = {}
        input_thread = Thread(target=self._get_input)
        submit_thread = Thread(target=self._submit_jobs)
        result_thread = Thread(target=self._get_results)
        input_thread.start()
        submit_thread.start()
        result_thread.start()


    def _get_input(self):

        while True:
            quantum_jobs = []
            start_time = time.time()
            experiments = 0

            while time.time() - start_time < self._batch_timeout and experiments < self._max_experiments*self._max_jobs:
                try:
                    quantum_job = self._input.get(timeout=min(5, self._batch_timeout))
                except Empty:
                    continue
                shots = quantum_job.shots
                reps = math.ceil(shots/self._max_shots)
                experiments += reps
                quantum_jobs.append(quantum_job)
                self._quantum_job_table[quantum_job.id] = quantum_job

            if len(quantum_jobs) > 0:
                self._addCircuits({job.id:{"circuit":job.circuit, "shots":job.shots} for job in quantum_jobs})

    def _addCircuits(self, circuits):
        """Generate a schedule constisting of ScheduleItems"""
        if len(circuits) == 0:
            return
        schedule_item = ScheduleItem(self._max_shots, self._max_experiments)
        for key, item in circuits.items():
            circuit = item["circuit"]
            shots = item["shots"]
            remaining_shots = schedule_item.add_circuit(key, circuit, shots)
            while remaining_shots > 0:
                self._log.info(f"Generated ScheduleItem {self._schedule_item_count}")
                self._schedule.put((self._schedule_item_count, schedule_item))
                self._schedule_item_count += 1
                schedule_item = ScheduleItem(self._max_shots, self._max_experiments)
                remaining_shots = schedule_item.add_circuit(key, circuit, remaining_shots)
        self._schedule.put((self._schedule_item_count, schedule_item))
        self._log.info(f"Generated ScheduleItem {self._schedule_item_count}")
        self._schedule_item_count += 1
        self._log.info("Added all circuits")
        


    

    def _submit_jobs(self):
        """Submit the circuits to the backend to execute them."""
        self._log.info("Start submitting jobs")
        n_workers = self._backend.job_limit().maximum_jobs
        executor =  ThreadPoolExecutor(n_workers)
        while True:
            index, item = self._schedule.get()
            future_job = executor.submit(self._submit_future_function, item, index)
            self._jobs.put((index, item, future_job))
                
    


    def _get_results(self):
        """Get the results for the submited jobs.

        Returns: 
            dict : A dictionary containing a mapping from keys to results
        """

        previous_memory = None
        previous_counts = None
        previous_key = None

        while True:
            index, schedule_item, future_job = self._jobs.get()
            job = future_job.result()
            job_result = job.result()
            

            result_for_item, previous_key, previous_memory, previous_counts = self._process_job_result(job_result, schedule_item, index, previous_key, previous_memory, previous_counts)
            for key, result in result_for_item.items():
                try:
                    job = self._quantum_job_table.pop(key)
                    job.result = result
                    self._results.put(job)
                except KeyError as ke:
                    # TODO Exception Handling
                    raise ke
