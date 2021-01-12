from itertools import count
from qiskit import execute, IBMQ, QuantumCircuit, Aer
from qiskit.result.result import Result
from aggregator import aggregate_q_jobs, split_results
from quantum_ciruit_object import Quantum_Job, session
from quantum_circuit_generator.generators import gen_BV
import numpy as np

def calc_chi_2(result, ground_truth: Result, statevector:bool=False):
    counts = result.get_counts()
    shots = sum(counts.values())
    if statevector:
        statevector = ground_truth.get_statevector()
        prob = [np.power(value.real, 2) + np.power(value.imag, 2) for value in statevector]
        counts = dict((int(key, 2), val/shots) for key, val in counts.items())
        chi_2 = 0
        for i, b in enumerate(prob):
            if i in counts:
                a = counts[i]
            else:
                a = 0
            chi_2 += np.power(a-b,2)/(a+b)
        return chi_2
    else:
        gt_counts = ground_truth.get_counts()
        gt_shots = sum(gt_counts.values())
        keys = list(set(counts.keys()) | set(gt_counts.keys()))
        chi_2 = 0
        for key in keys:
            if key in counts:
                a = counts[key]/shots
            else:
                a = 0
            if key in gt_counts:
                b = gt_counts[key]/gt_shots
            else:
                b = 0
            chi_2 += np.power(a-b,2)/(a+b)
        return chi_2


if __name__ == "__main__":

    provider = IBMQ.load_account()

    backend = provider.get_backend('ibmq_santiago')

    backend_sim = provider.get_backend('ibmq_qasm_simulator')

    backend_state = Aer.get_backend('statevector_simulator')


    # circ_1 = gen_BV('a')
    circ_2 = gen_BV('ab')

    circ_1 = QuantumCircuit(2, 2)
    circ_1.h(0)
    circ_1.h(1)


    job_1_state = execute(circ_1, backend_state)
    job_2_state = execute(circ_2, backend_state)


    # circ_1.measure_all()
    circ_2.measure_all()
    circ_1.measure([0,1], [0,1])

    #q_job = Quantum_Job(circ_a)
    q_job_1 = Quantum_Job(circ_1)
    q_job_2 = Quantum_Job(circ_2)

    session.add(q_job_1)
    session.add(q_job_2)
    session.commit()

    agg_job = aggregate_q_jobs([q_job_1, q_job_2])

    agg_circuit = agg_job.circuit

    print(agg_circuit)


    
    job_1 = execute(circ_1, backend, shots=8192)
    job_2 = execute(circ_2, backend, shots=8192)
    job_agg = execute(agg_circuit, backend, shots=8192)

    agg_job.qiskit_job_id = job_agg.job_id()

    res_agg = split_results(job_agg.result(), agg_job)

    res_1_agg = res_agg[0]
    res_2_agg = res_agg[1]

    res_1 = job_1.result()
    res_2 = job_2.result()

    res_1_state = job_1_state.result()
    res_2_state = job_2_state.result()

    print("\n" + 20*"*" + "Counts" + 20*"*")
    print(f"circ_1 count:{res_1.get_counts()}")
    print(f"circ_1_agg count:{res_1_agg.get_counts()}")
    print(f"circ_1_state count:{res_1_state.get_counts()}")
    print(f"circ_2 count:{res_2.get_counts()}")
    print(f"circ_2_agg count:{res_2_agg.get_counts()}")
    print(f"circ_2_state count:{res_2_state.get_counts()}")
    print(f"count:{job_agg.result().get_counts()}")

    print("\n" + 20*"*" + "Chi^2" + 20*"*")
    chi_2_1 = calc_chi_2(res_1, res_1_state, True)
    chi_2_1_agg = calc_chi_2(res_1_agg, res_1_state, True)
    chi_2_2 = calc_chi_2(res_2, res_2_state, True)
    chi_2_2_agg = calc_chi_2(res_2_agg, res_2_state, True)
    print(f"chi^2 of circ_1: {chi_2_1}")
    print(f"chi^2 of circ_1_agg: {chi_2_1_agg}")
    print(f"chi^2 of circ_2: {chi_2_2}")
    print(f"chi^2 of circ_2_agg: {chi_2_2_agg}")

