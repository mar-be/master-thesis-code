import math
import time
from concurrent.futures import ThreadPoolExecutor
from queue import Empty, Queue
from threading import Thread
from typing import Callable, List, Optional, Tuple

from qiskit.providers.provider import Provider

from quantum_job import QuantumJob

import logger
from qiskit.providers.basebackend import BaseBackend
from qiskit.providers import Backend, backend

from execution_handler.scheduler import (BackendControl, ScheduleItem,
                                         AbstractExecution)


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
            backend = job.backend_info["name"]
            if backend in self._backend_table.keys():
                self._backend_queue_table[backend].put(job)
            else:
                backend_queue = Queue()
                backend_queue.put(job)
                self._backend_queue_table[backend] = backend_queue
                self._new_backend.put((backend, backend_queue))
                

class Batch(ScheduleItem):
    
    def __init__(self, backen_name:str, max_shots: int, max_experiments: int):
        self.backend_name = backen_name
        super().__init__(max_shots, max_experiments)

class Batcher(Thread):

    def __init__(self, output: Queue, new_backend:Queue, get_max_batch_size:Callable[[str], int], get_max_shots:Callable[[str], int], batch_timeout:int=30) -> None:
        self._output = output
        self._new_backend = new_backend
        self._batch_timeout = batch_timeout
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
        batch = Batch(backend_name, self._backend_max_shots[backend_name], self._backend_max_batch_size[backend_name])
        for job in circuits:
            key = job.id
            circuit = job.circuit
            shots = job.shots
            remaining_shots = batch.add_circuit(key, circuit, shots)
            while remaining_shots > 0:
                self._log.info(f"Generated Batch {self._batch_count} for backend {backend_name}")
                self._output.append((self._batch_count, batch))
                self._batch_count += 1
                batch = Batch(backend_name, self._backend_max_shots[backend_name], self._backend_max_batch_size[backend_name])
                remaining_shots = batch.add_circuit(key, circuit, remaining_shots)
        self._output.append((self._batch_count, batch))
        self._log.info(f"Generated Batch {self._batch_count} for backend {backend_name}")
        self._batch_count += 1
        self._log.info(f"Added all circuits to batches for backend {backend_name}")

    def run(self) -> None:
        self._log.info("Started")
        while True:
            while not self._new_backend.empty:
                backend_name, backend_queue = self._new_backend.get()
                self._backend_queue_table[backend_name] = backend_queue
                self._backend_max_batch_size[backend_name] = self._get_max_batch_size(backend_name)
                self._backend_max_shots[backend_name] = self._get_max_shots(backend_name)

            for backend_name, backend_queue in self._backend_queue_table.items():
                if backend_queue.empty():
                    # nothimg to do since queue is empty
                    continue

                if not backend_name in self._queue_timers.keys():
                    # No timer is started but queue is not empty. Thus, start a timer.
                    self._queue_timers[backend_name] = time.time()
                
                if time.time() - self._queue_timers[backend_name] > self._batch_timeout or  backend_queue.qsize() >= self._backend_max_batch_size[backend_name]:
                    # Timeout occured or enough items for a wole batch -> try to get a batch
                    batch = []
                    for _ in range(self._backend_max_batch_size[backend_name]):
                        try:
                            batch.append(backend_queue.get(block=False))
                        except Empty:
                            break
                    self._output.put((backend_name, batch))
                    if backend_queue.empty():
                        # delete timer because the queue is empty
                        self._queue_timers[backend_name].pop()
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


class Submitter(AbstractBackendInteractor):

        
    def run(self) -> None:
        self._log.info("Started")
        while True:
            backend_name, batch = self._input.get()
            backend = self._get_backend(backend_name)

    


    

class Retriever(AbstractBackendInteractor):

    def run(self) -> None:
        self._log.info("Started")
        while True:
            self._input.get()


class ExecutionHandler(AbstractExecution):

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
