import numpy as np
import multiprocessing as mp

from qiskit_helper_functions.non_ibmq_functions import generate_circ, read_dict

from cutqc.main import CutQC
from cutqc.helper_fun import get_dirname

def qiskit_runtime_approx(full_circ_size):
    '''
    This approximation of Qiskit runtime is obtained from profiling its runtime
    Runtime may vary on different computers
    '''
    a = 4.66394101e-06
    b = 7.13570973e-01
    c = 3.18666818e-01
    return a * np.exp(b * full_circ_size) + c

def check_speedup(circuit_cases,num_threads,qubit_limit):
    # Check the CutQC's speedup
    for circuit_case in circuit_cases:
        circuit_name, max_subcircuit_qubit = circuit_case.split('|')
        circuit_type, full_circ_size = circuit_name.split('_')
        max_subcircuit_qubit = int(max_subcircuit_qubit)
        full_circ_size = int(full_circ_size)
        dest_folder = get_dirname(circuit_name=circuit_name,max_subcircuit_qubit=max_subcircuit_qubit,
                early_termination=1,num_threads=num_threads,eval_mode='runtime',qubit_limit=qubit_limit,field='build')
        summary = read_dict(filename='%s/summary.pckl'%dest_folder)
        qiskit_runtime = qiskit_runtime_approx(full_circ_size)
        print('%s: CutQC speedup = %.3fX'%(circuit_case,qiskit_runtime/summary['build_time_0']))

if __name__ == '__main__':
    # Generate some test circuits
    circuits = {}
    circuit_cases = []
    max_subcircuit_qubit = 15
    for full_circ_size in range(20,25):
        for circuit_type in ['supremacy','bv']:
            circuit_name = '%s_%d'%(circuit_type,full_circ_size)

            circuit = generate_circ(full_circ_size=full_circ_size,circuit_type=circuit_type)
            if circuit.num_qubits==0:
                continue
            else:
                circuits[circuit_name] = circuit
                circuit_cases.append('%s|%d'%(circuit_name,max_subcircuit_qubit))

    # Use CutQC package to evaluate the circuits
    num_threads = mp.cpu_count()
    qubit_limit = 24
    cutqc = CutQC(verbose=False)
    cutqc.cut(circuits=circuits,max_subcircuit_qubit=max_subcircuit_qubit,num_subcircuits=[2,3],max_cuts=10)
    cutqc.evaluate(circuit_cases=circuit_cases,eval_mode='runtime',num_nodes=1,num_threads=4,early_termination=[1],ibmq=None)
    cutqc.post_process(circuit_cases=circuit_cases,eval_mode='runtime',num_nodes=1,num_threads=num_threads,early_termination=1,qubit_limit=qubit_limit,recursion_depth=1)
    check_speedup(circuit_cases=circuit_cases,num_threads=num_threads,qubit_limit=qubit_limit)