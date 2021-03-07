import copy
import math
import os
import time
from collections import Counter
from queue import Empty, Queue
from threading import Lock, Thread, Timer
from typing import Dict, List
import logger
from qiskit import QuantumCircuit, assemble, transpile
from qiskit.providers import Backend
from qiskit.providers.ibmq.accountprovider import AccountProvider
from qiskit.providers.job import Job
from qiskit.providers.provider import Provider
from qiskit.qobj import Qobj
from qiskit.result.models import ExperimentResultData
from qiskit.result.result import Result
from quantum_job import QuantumJob
import concurrent.futures
import qiskit.tools.parallel

def new_parallel_map(task, values, task_args=tuple(), task_kwargs={}, num_processes=1):
    cpu_count = os.cpu_count()
    if cpu_count:
        num_processes = cpu_count
    return qiskit.tools.parallel.parallel_map(task, values, task_args, task_kwargs, num_processes)

transpile.__globals__["parallel_map"] = new_parallel_map

class BackendLookUp():

    def __init__(self, provider:Provider) -> None:
        self._log = logger.get_logger(type(self).__name__)
        self._provider = provider
        self._backends = {}

    def get(self, backend_name:str, exclusiv=False) -> Backend:
        if exclusiv:
            return self._provider.get_backend(backend_name)
        try:
            backend = self._backends[backend_name]
        except KeyError:
            backend = self._provider.get_backend(backend_name)
            self._log.info(f"Retrieved backend {backend_name}")
            self._backends[backend_name] = backend
        return backend

    def max_shots(self, backend_name:str) -> int:
        backend = self.get(backend_name)
        return backend.configuration().max_shots

    def max_experiments(self, backend_name:str) -> int:
        backend = self.get(backend_name)
        return backend.configuration().max_experiments


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

class TranspilerLookUp():

    def __init__(self, backend_look_up:BackendLookUp, min_circuits:int, timeout:int) -> None:
        self._backend_look_up = backend_look_up
        self._min_circuits = min_circuits
        self._timeout = timeout
        self._transpilers = {}

    def _get_or_create_transpiler(self, backend_name):
        try:
            return self._transpilers[backend_name]
            
        except KeyError:
            backend = self._backend_look_up.get(backend_name)
            backend.configuration()
            backend.properties()
            transpiler = Transpiler(Queue(), Queue(), backend, self._min_circuits, self._timeout)
            self._transpilers[backend_name] = transpiler
            transpiler.start()
            return transpiler

    def get_input(self, backend_name):
        return self._get_or_create_transpiler(backend_name).input

    def get_output(self, backend_name):
        return self._get_or_create_transpiler(backend_name).output

class TranspilerExecution():

    def __init__(self, backend_look_up:BackendLookUp, output:Queue, timeout:int) -> None:
        self._log = logger.get_logger(type(self).__name__)
        self._backend_look_up = backend_look_up
        self._output = output
        self._timeout = timeout
        self._jobs_to_transpile = {}
        self._timers = {}
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    
    def _transpile_func(self, jobs:List[QuantumJob], backend:Backend):
        circuits = list([job.circuit for job in jobs])
        self._log.debug(f"Start transpilation of {len(circuits)} circuits for backend {backend.name()}")
        trans_start_time = time.time()
        transpiled_circuits = transpile(circuits, backend=backend)
        time_diff = time.time() - trans_start_time
        self._log.info(f"Transpiled {len(transpiled_circuits)} circuits for backend {backend.name()} in {time_diff}s")
        return zip(transpiled_circuits, jobs)

    def _done_callback(self, future:concurrent.futures.Future):
        result = future.result()
        for transpile_tuple in result:
            self._output.put(transpile_tuple)

    def _transpile(self, backend_name):
        n_jobs = min(len(self._jobs_to_transpile[backend_name]), self._backend_look_up.max_experiments(backend_name))
        jobs = self._jobs_to_transpile[backend_name][:n_jobs]
        self._jobs_to_transpile[backend_name] = self._jobs_to_transpile[backend_name][n_jobs:]
        backend = self._backend_look_up.get(backend_name)
        backend.configuration()
        backend.properties()
        future =  self.executor.submit(self._transpile_func, jobs, backend)
        if len(self._jobs_to_transpile[backend_name]) > 0:
            timer = Timer(self._timeout, self._timer_func, [backend_name])
            timer.start()
            self._timers[backend_name] = timer
        future.add_done_callback(self._done_callback)
        
    
    def add_job(self, job:QuantumJob):
        backend_name = job.backend_data.name
        try:
            self._jobs_to_transpile[backend_name].append(job)
        except KeyError:
            self._jobs_to_transpile[backend_name] = [job]
        if len(self._jobs_to_transpile[backend_name]) == 1:
            timer = Timer(self._timeout, self._transpile, [backend_name])
            timer.start()
            self._timers[backend_name] = timer
        if len(self._jobs_to_transpile[backend_name]) == self._backend_look_up.max_experiments(backend_name):
            # Todo try to cancel
            self._timers[backend_name].cancel()
            self._transpile(backend_name)


class ExecutionSorter(Thread):

    def __init__(self, input:Queue, new_backend:Queue, transpiler_look_up:TranspilerLookUp):
        self._log = logger.get_logger(type(self).__name__)
        self._input = input
        self._new_backend = new_backend
        self._transpiler_look_up = transpiler_look_up
        self._backend_queue_table = {}
        Thread.__init__(self)
        self._log.info("Init")

    
    def run(self) -> None:
        self._log.info("Started")
        while True:
            job:QuantumJob = self._input.get()
            backend_name = job.backend_data.name
            if not backend_name in self._backend_queue_table.keys():
                transpiler_input = self._transpiler_look_up.get_input(backend_name)
                self._backend_queue_table[backend_name] = transpiler_input
                self._new_backend.put(backend_name)
                self._log.debug(f"Created new transpiler for backend {backend_name}")
            # self._log.debug(f"Sorted job {job.id} for backend {backend}")
            self._backend_queue_table[backend_name].put(job)

class Transpiler(Thread):
    def __init__(self, input:Queue, output:Queue, backend:Backend, min_circuits:int, timeout:int):
        self._log = logger.get_logger(type(self).__name__ + "_" + backend.name())
        self.input = input
        self.output = output
        self._backend = backend
        self._min_circuits = min_circuits
        self._max_circuits = backend.configuration().max_experiments
        self._timeout = timeout
        Thread.__init__(self)
        self._log.info("Init")


    def run(self) -> None:
        while True:
            start_time = time.time()
            jobs = []
            while len(jobs) < self._max_circuits and time.time() - start_time <= self._timeout:
                try:
                    job:QuantumJob = self.input.get(timeout=5)
                    jobs.append(job)                        
                except Empty:
                    if len(jobs) >= self._min_circuits:
                        break
            
            if len(jobs) > 0:
                circuits = list([job.circuit for job in jobs])
                self._log.debug(f"Start transpilation of {len(circuits)} circuits for backend {self._backend.name()}")
                trans_start_time = time.time()
                transpiled_circuits = transpile(circuits, backend=self._backend)
                time_diff = time.time() - trans_start_time
                self._log.info(f"Transpiled {len(transpiled_circuits)} circuits for backend {self._backend.name()} in {time_diff}s")
                for tuple in zip(transpiled_circuits, jobs):
                    self.output.put(tuple)

        


class Batch():
    '''A batch represents a job on a backend. It can contain multiple experiments.'''

    def __init__(self, backen_name:str, max_shots: int, max_experiments: int, batch_number:int):
        self._log = logger.get_logger(type(self).__name__)
        self.backend_name = backen_name
        self.max_shots = max_shots
        self.shots = 0
        self.max_experiments = max_experiments
        self.experiments = []
        self.remaining_experiments = max_experiments
        self.n_circuits = 0
        self.batch_number = batch_number

    
    def add_circuit(self, key, circuit:QuantumCircuit, shots:int) -> int:
        """Add a circuit to the Batch.

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
                

class Batcher(Thread):

    def __init__(self, output: Queue, new_backend:Queue, quantum_job_table:Dict, backend_look_up:BackendLookUp, transpiler_look_up:TranspilerLookUp, batch_timeout:int=30) -> None:
        self._log = logger.get_logger(type(self).__name__)
        self._output = output
        self._new_backend = new_backend
        self._batch_timeout = batch_timeout
        self._quantum_job_table = quantum_job_table
        self._backend_look_up = backend_look_up
        self._transpiler_look_up = transpiler_look_up
        self._backend_queue_table = {}
        self._backend_max_batch_size = {}
        self._backend_max_shots = {}
        self._queue_timers = {}
        self._batch_count = {}
        Thread.__init__(self)
        self._log.info("Init")

    def _create_batches(self, backend_name:str, transpiled_circuits:List[QuantumCircuit], jobs:List[QuantumJob]):
        """Generate a list of batches"""
        assert(len(transpiled_circuits)==len(jobs))
        self._log.debug(f"Adding {len(transpiled_circuits)} circuits to batches")
        if len(transpiled_circuits) == 0:
            return
        try:
            count = self._batch_count[backend_name]
        except KeyError:
            count = 0
            self._batch_count[backend_name] = 0

        batch = Batch(backend_name, self._backend_max_shots[backend_name], self._backend_max_batch_size[backend_name], count)
        for circuit, job in zip(transpiled_circuits, jobs):
            key = job.id
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
                backend_name = self._new_backend.get()
                transpiler_output = self._transpiler_look_up.get_output(backend_name)
                self._backend_queue_table[backend_name] = transpiler_output
                self._backend_max_batch_size[backend_name] = self._backend_look_up.max_experiments(backend_name)
                self._backend_max_shots[backend_name] = self._backend_look_up.max_shots(backend_name)
                self._log.debug(f"Got new backend {backend_name} with max batch size {self._backend_max_batch_size[backend_name]} and max shots {self._backend_max_shots[backend_name]}")

            for backend_name, backend_queue in self._backend_queue_table.items():
                if backend_queue.empty():
                    # nothimg to do since queue is empty
                    continue

                if not backend_name in self._queue_timers.keys():
                    # No timer is started but queue is not empty -> start a timer
                    self._queue_timers[backend_name] = time.time()
                
                if time.time() - self._queue_timers[backend_name] > self._batch_timeout or backend_queue.qsize() >= self._backend_max_batch_size[backend_name]:
                    # Timeout occured or enough items for a wole batch -> try to get a batch
                    self._log.debug(f"Time {time.time() - self._queue_timers[backend_name]}, timeout: {self._batch_timeout}, qsize:{backend_queue.qsize()}, max batch size {self._backend_max_batch_size[backend_name]}")
                    add_to_batch_circs = []
                    add_to_batch_jobs = []
                    for _ in range(self._backend_max_batch_size[backend_name]):
                        try:
                            transpiled_circ, job = backend_queue.get(block=False)
                            add_to_batch_circs.append(transpiled_circ)
                            add_to_batch_jobs.append(job)
                            self._quantum_job_table[job.id] = job
                        except Empty:
                            break
                    self._create_batches(backend_name, add_to_batch_circs, add_to_batch_jobs)
                    if backend_queue.empty():
                        # delete timer because the queue is empty
                        self._queue_timers.pop(backend_name)
                    else:
                        # start a new timer
                        self._queue_timers[backend_name] = time.time()


class Submitter(Thread):

    def __init__(self, input: Queue, output: Queue, backend_look_up:BackendLookUp, backend_control:BackendControl, defer_interval=60):
        self._log = logger.get_logger(type(self).__name__)
        self._input = input
        self._output = output
        self._backend_look_up = backend_look_up
        self._backend_control = backend_control
        self._defer_interval = defer_interval
        self._internal_jobs_queue = []
        Thread.__init__(self)
        self._log.info("Init")

    def _assemble(self, batch:Batch) -> Qobj:
        backend_name = batch.backend_name
        backend = self._backend_look_up.get(backend_name)
        circuits = list([circuit_item["circuit"] for circuit_item in batch.experiments])
        multiplied_circuits = []
        for i, circuit_item in enumerate(batch.experiments):
            reps = circuit_item["reps"]
            circ = circuits[i]
            multiplied_circuits.extend([circ]*reps)
        #self._log.info(f"Transpiled batch {backend_name}/{batch.batch_number}")
        qobj =  assemble(multiplied_circuits, backend, shots=batch.shots, memory=True)
        self._log.info(f"Assembled Qobj for batch {backend_name}/{batch.batch_number}")
        return qobj

        
    def run(self) -> None:
        self._log.info("Started")
        batch: Batch
        qobj: Qobj
        while True:
            try:
                batch = self._input.get(timeout=self._defer_interval)
                qobj = self._assemble(batch)
                self._internal_jobs_queue.append((batch, qobj))
            except Empty:
                pass
            deferred_jobs = []
            for batch, qobj in self._internal_jobs_queue:
                backend_name = batch.backend_name
                backend = self._backend_look_up.get(backend_name)
                if self._backend_control.try_to_enter(backend_name, backend):
                    job = backend.run(qobj)
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




    

class ResultProcessor(Thread):

    def __init__(self, input: Queue, output: Queue, quantum_job_table:Dict):
        self._log = logger.get_logger(type(self).__name__)
        self._input = input
        self._output = output
        self._quantum_job_table = quantum_job_table
        self._previous_key = {}
        self._previous_memory = {}
        self._previous_counts = {}
        Thread.__init__(self)
        self._log.info("Init") 

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
    
    def __init__(self, provider:AccountProvider, input:Queue, output:Queue, batch_timeout:int = 60, retrieve_time:int = 30) -> None:
        new_backends = Queue()
        batcher_submitter = Queue()
        submitter_retrieber = Queue()
        retriever_processor = Queue()
        quantum_job_table = {}
        backend_look_up = BackendLookUp(provider)
        backend_control = BackendControl()
        transpiler_look_up = TranspilerLookUp(backend_look_up, 10, 15)
        self._execution_sorter = ExecutionSorter(input, new_backends, transpiler_look_up)
        self._batcher = Batcher(batcher_submitter, new_backends, quantum_job_table, backend_look_up, transpiler_look_up, batch_timeout)
        self._submitter = Submitter(input=batcher_submitter, output=submitter_retrieber, backend_look_up=backend_look_up, backend_control=backend_control, defer_interval=5)
        self._retriever = Retriever(input=submitter_retrieber, output=retriever_processor, wait_time=retrieve_time, backend_control=backend_control)
        self._processor = ResultProcessor(input=retriever_processor, output=output, quantum_job_table=quantum_job_table)
    
    def start(self):
        self._execution_sorter.start()
        self._batcher.start()
        self._submitter.start()
        self._retriever.start()
        self._processor.start()
