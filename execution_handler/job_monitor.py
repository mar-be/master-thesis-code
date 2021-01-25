import threading
from typing import List, Union
from qiskit.providers.basejob import BaseJob
from qiskit.providers.job import JobV1
import time



class Job_Monitor(threading.Thread):

    def __init__(self, wait:float) -> None:
        threading.Thread.__init__(self)
        self.jobs: List[Union[BaseJob, JobV1]] = []
        self.wait = wait
        self.start()

    def add(self, job:Union[BaseJob, JobV1]):
        self.jobs.append(job)


    def run(self):
        while True:
            final_state_jobs = []
            for job in self.jobs:
                if job.in_final_state():
                    final_state_jobs.append(job)
            self.__process_final_state(final_state_jobs)
            time.sleep(self.wait)

    def __process_final_state(self, jobs:List[Union[BaseJob, JobV1]]):
        for job in jobs:
            self.jobs.remove(job)
       
            # Grab results from the job
            result = job.result()
            print(result.job_id)
            print(result.get_counts())