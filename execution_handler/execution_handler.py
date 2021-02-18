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
        self._batch_count = {}
        Thread.__init__(self)
        self._log.info("Init")

    def _create_batches(self, backend_name:str, circuits:List[QuantumJob]):
        """Generate a list of batches"""
        if len(circuits) == 0:
            return
        try:
            count = self._batch_count[backend_name]
        except KeyError:
            count = 0
            self._batch_count[backend_name] = 0

        batch = Batch(backend_name, self._backend_max_shots[backend_name], self._backend_max_batch_size[backend_name], count)
        for job in circuits:
            key = job.id
            circuit = job.circuit
            shots = job.shots
            remaining_shots = batch.add_circuit(key, circuit, shots)
            while remaining_shots > 0:
                self._log.info(f"Generated for backend {backend_name} batch {self._batch_count[backend_name]}")
                self._output.put(batch)
                self._batch_count[backend_name] += 1
                batch = Batch(backend_name, self._backend_max_shots[backend_name], self._backend_max_batch_size[backend_name], self._batch_count[backend_name])
                remaining_shots = batch.add_circuit(key, circuit, remaining_shots)
        self._log.info(f"Generated for backend {backend_name} batch {self._batch_count[backend_name]}")
        self._output.put(batch)
        self._batch_count[backend_name] += 1
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
        transpiled_circuits = transpile(circuits_to_execute, backend=backend)
        self._log.info(f"Transpiled batch {backend_name}/{batch.batch_number}")
        qobj =  assemble(transpiled_circuits, backend, shots=batch.shots, memory=True)
        self._log.info(f"Assembled Qobj for batch {backend_name}/{batch.batch_number}")
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
                        # self._log.debug(f"Qobj is not yet available -> defer job for batch {batch.backend_name}/{batch.batch_number}")
                        deferred_jobs.append((batch, qobj))
                        continue
                backend_name = batch.backend_name
                backend = self._get_backend(backend_name)
                if self._backend_control.try_to_enter(backend_name, backend):
                    job = self._submit(batch.backend_name, qobj)
                    self._log.info(f"Submitted batch {batch.batch_number} to {batch.backend_name}")
                    self._output.put((batch, job))
                else:
                    # self._log.debug(f"Reached limit of queued jobs for backend {backend_name} -> defer job for batch {batch.batch_number}")
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
        self._batch_counter = {}
        self._deferred_results = {}   
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
                batch, job = job_tuple
                self._log.info(f"Received result for batch {batch.backend_name}/{batch.batch_number}")
                try:
                    batch_counter = self._batch_counter[batch.backend_name]
                except KeyError:
                    batch_counter = 0
                    self._batch_counter[batch.backend_name] = 0
                    self._deferred_results[batch.backend_name] = []
                if batch_counter == batch.batch_number:
                    # the received batch is the next batch -> output it
                    batch_counter += 1
                    self._output.put(job_tuple)
                    # check if deferred results can be output
                    if len(self._deferred_results[batch.backend_name]) > 0:
                        # sort the deferred job tuples according to their batch number
                        self._deferred_results[batch.backend_name].sort(key=lambda tuple:tuple[0].batch_number)
                    while len(self._deferred_results[batch.backend_name]) > 0 and batch_counter == self._deferred_results[batch.backend_name][0][0].batch_number:
                        # ouput jobs as long as their are deferred jobs and the batch number is next following number
                        self._output.put(self._deferred_results[batch.backend_name].pop(0))
                        batch_counter += 1
                    
                    self._batch_counter[batch.backend_name] = batch_counter
                else:
                    # the received batch is not the next batch
                    self._deferred_results[batch.backend_name].append(job_tuple)
                    self._log.info(f"Deferred result for batch {batch.backend_name}/{batch.batch_number} to establish order")

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
        self._submitter = Submitter(input=assembler_submitter, output=submitter_retrieber, provider=provider, backend_control=backend_control, defer_interval=1)
        self._retriever = Retriever(input=submitter_retrieber, output=retriever_processor, wait_time=retrieve_time, backend_control=backend_control)
        self._processor = ResultProcessor(input=retriever_processor, output=output, provider=provider, quantum_job_table=quantum_job_table)
    
    def start(self):
        self._execution_sorter.start()
        self._batcher.start()
        self._assembler.start()
        self._submitter.start()
        self._retriever.start()
        self._processor.start()
