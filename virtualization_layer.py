from typing import Dict
from partitioner.partition_result_processing import ResultProcessing, ResultWriter
from resource_mapping.result_analyzer import ResultAnalyzer
from execution_handler.execution_handler import ExecutionHandler
from partitioner.partitioner import Partitioner
from aggregator.aggregator import Aggregator, AggregatorResults
from resource_mapping.quantum_resource_mapper import QuantumResourceMapper
from resource_mapping.backend_chooser import Backend_Chooser
from queue import Queue

from qiskit.providers.provider import Provider
import logger

class Virtual_Execution_Environment():

    def __init__(self, provider: Provider, config:Dict) -> None:
        self._log = logger.get_logger(type(self).__name__)


        self.input = Queue()
        self.output = Queue()
        self.errors = Queue()

        input_execution = Queue()
        output_execution = Queue()

        input_aggregation = Queue()
        input_partition = Queue()

        input_aggregation_result = Queue()
        input_partition_result = Queue()
        all_results_are_available = Queue()



        aggregation_dict = {}
        partition_dict = {}

        self.backend_chooser = Backend_Chooser(provider, config["quantum_resource_mapper"]["backend_chooser"])
        self.quantum_resource_mapper = QuantumResourceMapper(input=self.input, output=input_execution, output_agg=input_aggregation, output_part=input_partition, backend_chooser=self.backend_chooser, config=config["quantum_resource_mapper"])
        self.aggregator = Aggregator(input=input_aggregation, output=input_execution, job_dict=aggregation_dict, timeout=config["aggregator"]["timeout"])
        self.partitioner = Partitioner(input=input_partition, output=input_execution, partition_dict=partition_dict, error_queue=self.errors, **config["partitioner"])
        self.execution_handler = ExecutionHandler(provider, input=input_execution, output=output_execution, **config["execution_handler"])
        self.result_analyzer = ResultAnalyzer(input=output_execution, output=self.output, output_agg=input_aggregation_result, output_part=input_partition_result)
        self.aggregation_result_processor = AggregatorResults(input=input_aggregation_result, output=self.output, job_dict=aggregation_dict)
        self.partition_result_writer = ResultWriter(input=input_partition_result, completed_jobs=all_results_are_available, partition_dict=partition_dict)
        self.partition_result_processor = ResultProcessing(input=all_results_are_available, output=self.output, partition_dict=partition_dict)

    
    def start(self):
        self.quantum_resource_mapper.start()
        self.aggregator.start()
        self.partitioner.start()
        self.execution_handler.start()
        self.result_analyzer.start()
        self.aggregation_result_processor.start()
        self.partition_result_writer.start()
        self.partition_result_processor.start()
