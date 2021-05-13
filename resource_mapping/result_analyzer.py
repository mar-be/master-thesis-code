from queue import Queue
from threading import Thread

import logger
from quantum_execution_job import Execution_Type, QuantumExecutionJob


class ResultAnalyzer(Thread):
    """Routes the results based on their execution type
    """
    
    def __init__(self, input:Queue, output:Queue, output_agg:Queue, output_part:Queue) -> None:
        self._log = logger.get_logger(type(self).__name__)
        self._input = input
        self._output = output
        self._output_agg = output_agg
        self._output_part = output_part
        Thread.__init__(self)
        self._log.info("Init ResultAnalyzer")

    def run(self) -> None:
        self._log.info("Started ResultAnalyzer")
        while True:
            job:QuantumExecutionJob = self._input.get()
            #self._log.debug(f"Got job {job.id}")
            if job.type == Execution_Type.raw:
                #self._log.debug(f"Put job {job.id} in output queue")
                self._output.put(job)
            elif job.type == Execution_Type.aggregation:
                #self._log.debug(f"Put job {job.id} in aggregation queue")
                self._output_agg.put(job)
            elif job.type == Execution_Type.partition:
                #self._log.debug(f"Put job {job.id} in partition queue")
                self._output_part.put(job)
            else:
                self._log.error("Unkown Execution_Type")
