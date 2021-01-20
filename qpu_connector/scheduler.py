import math
import copy

from collections import Counter

from qiskit import QuantumCircuit, execute, IBMQ
from qiskit.compiler import assemble
from qiskit.result.models import ExperimentResultData
from qiskit.result.postprocess import format_level_2_memory
from qiskit.result.result import Result
from qiskit.result.utils import marginal_counts



def _add_dicts(d1, d2):
    c = Counter(d1)
    c.update(d2)
    return dict(c)


class ScheduleItem():
    '''A schedule item represents a job on a backend. It can contain multiple experiments.'''

    def __init__(self, max_shots: int, max_experiments: int):
        self.max_shots = max_shots
        self.shots = 0
        self.max_experiments = max_experiments
        self.experiments = []
        self.n_experiments = 0
        self.remaining_experiments = max_experiments
        self.n_circuits = 0

    
    def add_circuit(self, key, circuit:QuantumCircuit, shots:int) -> int:
        """Add a circuit to the ScheduleItem.

        Args:
            key (Any): Identifier for the circuit
            circuit (QuantumCircuit): The circuit, which should be executed
            shots (int): The number of shots
    
        Returns:
            int: remaining shots. If they are 0, all shots are executed
        """
        self.n_circuits += 1
        reps = math.ceil(shots/self.max_shots)
        self.shots = min(shots, self.max_shots)

        if reps <= self.remaining_experiments:
            remaining_shots = 0
        else:
            reps = self.remaining_experiments
            remaining_shots = shots - reps*self.max_shots

        self.remaining_experiments -= reps
        self.experiments.append({"key":key, "circuit":circuit, "reps":reps, "shots":shots-remaining_shots, "total_shots":shots})
        
        return remaining_shots

    
class Scheduler():

    def __init__(self, circuits, backend, max_shots=None, max_experiments=None):
        self.circuits = circuits
        self.backend = backend
        if max_shots != None:
            self.max_shots = max_shots
        else:
            self.max_shots = backend.configuration().max_shots
        if max_experiments != None:
            self.max_experiments = max_experiments
        else:
            self.max_experiments = backend.configuration().max_experiments
        self.schedule = []
        self.jobs = []
        self._generate_schedule()

    def _generate_schedule(self):
        """Generate a schedule constisting of ScheduleItems"""
        if len(self.circuits) == 0:
            return
        schedule_item = ScheduleItem(self.max_shots, self.max_experiments)
        self.schedule.append(schedule_item)
        for key, item in self.circuits.items():
            circuit = item["circuit"]
            shots = item["shots"]
            remaining_shots = schedule_item.add_circuit(key, circuit, shots)
            while remaining_shots > 0:
                schedule_item = ScheduleItem(self.max_shots, self.max_experiments)
                self.schedule.append(schedule_item)
                remaining_shots = schedule_item.add_circuit(key, circuit, remaining_shots)

    def submit_jobs(self):
        """Submit the circuits to the backend to execute them."""
        circuits_to_execute = []
        for item in self.schedule:
            for circuit_item in item.experiments:
                circ = circuit_item["circuit"]
                reps = circuit_item["reps"]
                circuits_to_execute.extend([circ]*reps)
            job = execute(circuits_to_execute, self.backend, shots=item.shots, memory=True)
            self.jobs.append(job)



    def get_results(self):
        """Get the results for the submited jobs.

        Returns: 
            dict : A dictionary containing a mapping from keys to results
        """
        job_results = [job.result() for job in self.jobs]
        assert(len(job_results)==len(self.schedule))
        exp_results_dict = {}
        exp_number = 0
        previous_memory = None
        previous_counts = None
        previous_key = None
        success = True
        for index, schedule_item in enumerate(self.schedule):
            job_result = job_results[index]
            success = success and job_result.success
            max_shots = schedule_item.max_shots
            
            # get the Result as dict and delete the results 
            result_dict = job_result.to_dict()
            result_dict.pop("results")

            for exp in schedule_item.experiments:
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
                        counts = _add_dicts(counts, cnts)
                        # TODO trim counts w.r.t. number of shots
                    
                    if shots < total_shots:
                        previous_memory = copy.deepcopy(memory)
                        previous_counts = copy.deepcopy(counts)
                        previous_key = key
                        continue
                    
                    result_data = ExperimentResultData(counts=counts, memory=memory[:total_shots]).to_dict()

                    job_exp_result_dict["data"] = result_data
                    job_exp_result_dict["shots"] = total_shots

                exp_results_dict[key] = copy.deepcopy(result_dict)
                exp_results_dict[key]["results"] = [job_exp_result_dict]
                exp_number += reps

        return {key:Result.from_dict(value) for key, value in exp_results_dict.items()}



    
if __name__ == "__main__":

    provider = IBMQ.load_account()

    backend = provider.get_backend('ibmq_athens')

    backend_sim = provider.get_backend('ibmq_qasm_simulator')

    from qiskit.circuit.random import random_circuit


    circs = {i:{"circuit":random_circuit(5, 5 , measure=True), "shots":10000} for i in range(30)}

    scheduler = Scheduler(circs, backend_sim)
    scheduler.submit_jobs()
    res = scheduler.get_results()
    for i in range(len(circs)):
        c = circs[i]["circuit"]
        r = res[i]
        print(i, r.get_counts(c))