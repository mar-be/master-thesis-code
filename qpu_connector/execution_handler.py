from typing import List
from qpu_connector.scheduler import ExecutionHandler
from queue import Empty, Queue
import threading
import time
import math

from qiskit.providers.basebackend import BaseBackend

class Execution_Handler(threading.Thread):
    
    def __init__(self, backend: BaseBackend, input, output: Queue, batch_timeout: int):
        self._backend = backend
        self._max_experiments = backend.configuration().max_experiments*backend.job_limit().maximum_jobs
        self._max_shots = backend.configuration().max_shots
        self._input = input
        self._output = output
        self._batch_timeout = batch_timeout
        self._scheduler = ExecutionHandler(backend, output)
        threading.Thread.__init__(self)

    def run(self) -> None:
        while True:
            circuits = self._get_input()
            self._scheduler.addCircuits(circuits)


    

    def _get_input(self) -> List[dict]:
        circuits = []
        start_time = time.time()
        experiments = 0

        while time.time() - start_time < self._batch_timeout and experiments < self._max_experiments:
            try:
                circuit = self._input.get(timeout=5)
            except Empty:
                continue
            shots = circuit["shots"]
            reps = math.ceil(shots/self._max_shots)
            experiments += reps
            circuits.append(circuit)

        return {i:circ for i, circ in enumerate(circuits)}
        

