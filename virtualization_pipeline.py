from queue import Queue

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

    input = Queue()
    output = Queue()

    input_execution = Queue()
    output_execution = Queue()

    input_aggregation = Queue()
    input_partition = Queue()

    input_aggregation_result = Queue()
    input_partition_result = Queue()
    all_results_are_available = Queue()



    aggregation_dict = {}
    partition_dict = {}

    provider = IBMQ.load_account()

    backend_chooser = Backend_Chooser(provider)
    circuit_analyzer = CircuitAnalyzer(input=input, output=input_execution, output_agg=input_aggregation, output_part=input_partition, backend_chooser=backend_chooser)
    aggregator = Aggregator(input=input_aggregation, output=input_execution, job_dict=aggregation_dict, timeout=60)
    partitioner = Partitioner(input=input_partition, output=input_execution, partition_dict=partition_dict, num_subcircuits=[2,3], max_cuts=10)
    execution_handler = ExecutionHandler(provider, input=input_execution, output=output_execution)
    result_analyzer = ResultAnalyzer(input=output_execution, output=output, output_agg=input_aggregation_result, output_part=input_partition_result)
    aggregation_result_processor = AggregatorResults(input=input_aggregation_result, output=output, job_dict=aggregation_dict)
    partition_result_writer = ResultWriter(input=input_partition_result, completed_jobs=all_results_are_available, partition_dict=partition_dict)
    partition_result_processor = ResultProcessing(input=all_results_are_available, output=output, partition_dict=partition_dict)

    circuit_analyzer.start()
    aggregator.start()
    partitioner.start()
    execution_handler.start()
    result_analyzer.start()
    aggregation_result_processor.start()
    partition_result_writer.start()
    partition_result_processor.start()

    input.put(QuantumJob(random_circuit(6, 5, 2), shots=10000))
    input.put(QuantumJob(random_circuit(5, 5, 2), shots=10000))
    input.put(QuantumJob(random_circuit(5, 5, 2), shots=10000))
    input.put(QuantumJob(random_circuit(2, 5, 2), shots=10000))
    input.put(QuantumJob(random_circuit(2, 5, 2), shots=10000))

    i = 0
    while True:
        job = output.get() 
        log.info(job)
        i += 1
