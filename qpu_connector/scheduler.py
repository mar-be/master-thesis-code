from qiskit import QuantumCircuit, execute, IBMQ
import math

class ScheduleItem():

    def __init__(self, max_shots: int, max_experiments: int):
        self.max_shots = max_shots
        self.shots = 0
        self.max_experiments = max_experiments
        self.experiments = []
        self.n_experiments = 0
        self.remaining_experiments = max_experiments
        self.n_circuits = 0

    
    def add_circuit(self, key, circuit:QuantumCircuit, shots:int) -> int:
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
                remaining_shots = schedule_item.add_circuit(key, circuit, shots)

    def submit_jobs(self):
        circuits_to_execute = []
        for item in self.schedule:
            for circuit_item in item.experiments:
                circ = circuit_item["circuit"]
                reps = circuit_item["reps"]
                circuits_to_execute.extend([circ]*reps)
            job = execute(circuits_to_execute, self.backend, shots=item.shots, memory=True)
            self.jobs.append(job)



    def get_results(self):
        results = [job.result() for job in self.jobs]
        assert(len(results)==len(self.schedule))
        memory = {}
        exp_number = 0
        for index, schedule_item in enumerate(self.schedule):
            result = results[index]
            for exp in schedule_item.experiments:
                key = exp["key"]
                circ = exp["circuit"]
                reps = exp["reps"]
                shots = exp["shots"]
                for exp_index in range(exp_number, exp_number+reps):
                    mem = result.get_memory(exp_index)
                    if key in memory:
                        memory[key] += mem
                    else:
                        memory[key] = mem
                memory[key] = memory[key][:shots]
                exp_number += reps
        
        for key in memory:
            print(len(memory[key]))


if __name__ == "__main__":

    provider = IBMQ.load_account()

    backend = provider.get_backend('ibmq_athens')

    backend_sim = provider.get_backend('ibmq_qasm_simulator')

    from qiskit.circuit.random import random_circuit


    circs = {i:{"circuit":random_circuit(5, 5 , measure=True), "shots":10000} for i in range(30)}

    scheduler = Scheduler(circs, backend_sim)
    scheduler.submit_jobs()
    scheduler.get_results()

    

    