import math
import time
from concurrent.futures import ThreadPoolExecutor
from queue import Empty, Queue
from threading import Thread
from time import sleep
from typing import Optional

import logger
from qiskit import assemble, execute, transpile
from qiskit.compiler import assemble
from qiskit.providers import Job
from qiskit.providers.basebackend import BaseBackend

from execution_handler.scheduler import (BackendControl, ScheduleItem,
                                         AbstractExecution)

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
                    quantum_job = self._input.get(timeout=5)
                except Empty:
                    continue
                shots = quantum_job.shots
                reps = math.ceil(shots/self._max_shots)
                experiments += reps
                quantum_jobs.append(quantum_job)
                self._quantum_job_table[quantum_job.id] = quantum_job

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
