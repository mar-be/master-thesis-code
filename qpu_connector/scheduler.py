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
            shots_last_rep = shots - (reps - 1)*self.max_shots
            shots = 0
        else:
            reps = self.remaining_experiments
            shots_last_rep = self.max_shots
            shots -= reps*self.max_shots

        self.remaining_experiments -= reps
        self.experiments.append({"key":key, "circuit":circuit, "reps":reps, "shots_last_rep":shots_last_rep})
        
        return shots

    
class Scheduler():

    def __init__(self, circuits, backend, max_shots, max_experiments):
        self.circuits = circuits
        self.backend = backend
        self.max_shots = max_shots
        self.max_experiments = max_experiments
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
            job = execute(circuits_to_execute, self.backend, shots=item.shots)
            self.jobs.append(job)



    def get_results(self):
        for index, job in enumerate(self.jobs):
            schedule_item = self.schedule[index]
            res = job.result()
            print(res.get_counts())


if __name__ == "__main__":

    provider = IBMQ.load_account()

    backend = provider.get_backend('ibmq_athens')

    backend_sim = provider.get_backend('ibmq_qasm_simulator')

    from qiskit.circuit.random import random_circuit


    circs = {i:{"circuit":random_circuit(5, 5 , measure=True), "shots":10000} for i in range(30)}

    scheduler = Scheduler(circs, backend_sim, 8192, 50)
    scheduler.submit_jobs()
    scheduler.get_results()

    

    