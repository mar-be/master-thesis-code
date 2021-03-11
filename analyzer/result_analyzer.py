from quantum_job import Modification_Type, QuantumJob
from queue import Queue
from threading import Thread
import logger

class ResultAnalyzer(Thread):
    
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
            job:QuantumJob = self._input.get()
            #self._log.debug(f"Got job {job.id}")
            if job.type == Modification_Type.none:
                #self._log.debug(f"Put job {job.id} in output queue")
                self._output.put(job)
            elif job.type == Modification_Type.aggregation:
                #self._log.debug(f"Put job {job.id} in aggregation queue")
                self._output_agg.put(job)
            elif job.type == Modification_Type.partition:
                #self._log.debug(f"Put job {job.id} in partition queue")
                self._output_part.put(job)
            else:
                self._log.error("Unkown Modification_Type")