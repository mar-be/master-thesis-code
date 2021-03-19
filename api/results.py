from queue import Empty, Queue
from threading import Thread

import logger

import api.db_models


class ResultFetcher(Thread):
    
    def __init__(self, tasks:Queue, errors:Queue) -> None:
        self._log = logger.get_logger(type(self).__name__)
        self._tasks = tasks
        self._errors = errors
        Thread.__init__(self)

    
    def run(self) -> None:
        while True:
            while not self._errors.empty():
                try:
                    error_job = self._errors.get(block=False)
                    error_task = api.db_models.Task.objects(qjob_id=error_job.id).first()
                    error_task.status = "failed"
                    error_task.save()
                except Empty:
                    break
            try:
                job = self._tasks.get(timeout=10)
                task = api.db_models.Task.objects(qjob_id=job.id).first()
                task.status = "done"
                #TODO copy results
                task.update_results(job)
                task.save()
                self._log.info(f"Received result for task {task.id}")
            except Empty:
                continue
