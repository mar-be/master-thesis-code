from itertools import count
from qiskit import execute, IBMQ, QuantumCircuit
from qiskit.result.result import Result
from aggregator import aggregate_q_jobs, split_results
from quantum_ciruit_object import Quantum_Job, session
from quantum_circuit_generator.generators import gen_BV

def calc_chi_2(result, ground_truth: Result):
    counts = result.get_counts()
    shots = sum(counts.values())
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
        chi_2 += (a-b)**2/(a+b)
    return chi_2

if __name__ == "__main__":
    circ_a = gen_BV('a')
    circ_ab = gen_BV('ab')

    circ_a.measure_all()
    circ_ab.measure_all()

    print(circ_a)
    print(circ_ab)

    # Create a Quantum Circuit acting on the q register
    circuit = QuantumCircuit(2, 2)
    circuit.h(0)
    circuit.h(1)
    circuit.measure([0,1], [0,1])

    #q_job = Quantum_Job(circ_a)
    q_job = Quantum_Job(circuit)
    q_job2 = Quantum_Job(circ_ab)

    session.add(q_job)
    session.add(q_job2)
    session.commit()

    agg_job = aggregate_q_jobs([q_job, q_job2])

    agg_circuit = agg_job.circuit

    print(agg_circuit)

    provider = IBMQ.load_account()

    backend = provider.get_backend('ibmq_santiago')

    backend_sim = provider.get_backend('ibmq_qasm_simulator')


    job_a_sim = execute(circuit, backend_sim, shots=8192)
    job_ab_sim = execute(circ_ab, backend_sim, shots=8192)

    job_a = execute(circuit, backend, shots=8192)
    job_ab = execute(circ_ab, backend, shots=8192)
    job_agg = execute(agg_circuit, backend, shots=8192)

    agg_job.qiskit_job_id = job_agg.job_id()

    res_agg = split_results(job_agg.result(), agg_job)

    res_a_agg = res_agg[0]
    res_ab_agg = res_agg[1]

    res_a = job_a.result()
    res_ab = job_ab.result()

    res_a_sim = job_a_sim.result()
    res_ab_sim = job_ab_sim.result()

    print("\n" + 20*"*" + "Counts" + 20*"*")
    print(f"a count:{res_a.get_counts()}")
    print(f"a_agg count:{res_a_agg.get_counts()}")
    print(f"a_sim count:{res_a_sim.get_counts()}")
    print(f"ab count:{res_ab.get_counts()}")
    print(f"ab_agg count:{res_ab_agg.get_counts()}")
    print(f"ab_sim count:{res_ab_sim.get_counts()}")
    print(f"count:{job_agg.result().get_counts()}")

    print("\n" + 20*"*" + "Chi^2" + 20*"*")
    chi_2_a = calc_chi_2(res_a, res_a_sim)
    chi_2_ab = calc_chi_2(res_ab, res_ab_sim)
    print(f"chi^2 of a: {chi_2_a}")
    print(f"chi^2 of ab: {chi_2_ab}")
    chi_2_a_agg = calc_chi_2(res_a_agg, res_a_sim)
    chi_2_ab_agg = calc_chi_2(res_ab_agg, res_ab_sim)
    print(f"chi^2 of a_agg: {chi_2_a_agg}")
    print(f"chi^2 of ab_agg: {chi_2_ab_agg}")

