from queue import Queue
from virtualization_layer import Virtualization_Layer

from qiskit import IBMQ
from qiskit.circuit.random.utils import random_circuit

import logger
from aggregator.aggregator import Aggregator, AggregatorResults
from analyzer.backend_chooser import Backend_Chooser
from analyzer.circuit_analyzer import CircuitAnalyzer
from analyzer.result_analyzer import ResultAnalyzer
from execution_handler.execution_handler import ExecutionHandler
from partitioner.partition_result_processing import (ResultProcessing,
                                                     ResultWriter)
from partitioner.partitioner import Partitioner
from quantum_job import QuantumJob

if __name__ == "__main__":

    log = logger.get_logger("Virtualization")

    provider = IBMQ.load_account()

    vl = Virtualization_Layer(provider)

    input = vl.input
    output = vl.output

    vl.start()

    input.put(QuantumJob(random_circuit(16, 5, 2, measure=True), shots=10000))
    input.put(QuantumJob(random_circuit(5, 5, 2, measure=True), shots=10000))
    input.put(QuantumJob(random_circuit(5, 5, 2, measure=True), shots=10000))
    input.put(QuantumJob(random_circuit(2, 5, 2, measure=True), shots=10000))
    input.put(QuantumJob(random_circuit(2, 5, 2, measure=True), shots=10000))

    i = 0
    while True:
        job = output.get() 
        log.info(job.result_prob)
        i += 1
