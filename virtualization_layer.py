from partitioner.partition_result_processing import ResultProcessing, ResultWriter
from analyzer.result_analyzer import ResultAnalyzer
from execution_handler.execution_handler import ExecutionHandler
from partitioner.partitioner import Partitioner
from aggregator.aggregator import Aggregator, AggregatorResults
from analyzer.circuit_analyzer import CircuitAnalyzer
from analyzer.backend_chooser import Backend_Chooser
from queue import Queue

from qiskit.providers.provider import Provider
import logger

class Virtualization_Layer():

    def __init__(self, provider: Provider, aggregation_timeout:int=60, batch_timeout:int=60, retrieve_time:int=30, num_subcircuits=[2,3], max_cuts=10) -> None:
        self._log = logger.get_logger(type(self).__name__)

        self.input = Queue()
        self.output = Queue()

        input_execution = Queue()
        output_execution = Queue()

        input_aggregation = Queue()
        input_partition = Queue()

        input_aggregation_result = Queue()
        input_partition_result = Queue()
        all_results_are_available = Queue()



        aggregation_dict = {}
        partition_dict = {}

        self.backend_chooser = Backend_Chooser(provider)
        self.circuit_analyzer = CircuitAnalyzer(input=self.input, output=input_execution, output_agg=input_aggregation, output_part=input_partition, backend_chooser=self.backend_chooser)
        self.aggregator = Aggregator(input=input_aggregation, output=input_execution, job_dict=aggregation_dict, timeout=aggregation_timeout)
        self.partitioner = Partitioner(input=input_partition, output=input_execution, partition_dict=partition_dict, num_subcircuits=num_subcircuits, max_cuts=max_cuts)
        self.execution_handler = ExecutionHandler(provider, input=input_execution, output=output_execution, batch_timeout=batch_timeout, retrieve_time=retrieve_time)
        self.result_analyzer = ResultAnalyzer(input=output_execution, output=self.output, output_agg=input_aggregation_result, output_part=input_partition_result)
        self.aggregation_result_processor = AggregatorResults(input=input_aggregation_result, output=self.output, job_dict=aggregation_dict)
        self.partition_result_writer = ResultWriter(input=input_partition_result, completed_jobs=all_results_are_available, partition_dict=partition_dict)
        self.partition_result_processor = ResultProcessing(input=all_results_are_available, output=self.output, partition_dict=partition_dict)

    
    def start(self):
        self.circuit_analyzer.start()
        self.aggregator.start()
        self.partitioner.start()
        self.execution_handler.start()
        self.result_analyzer.start()
        self.aggregation_result_processor.start()
        self.partition_result_writer.start()
        self.partition_result_processor.start()