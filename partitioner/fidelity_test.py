import numpy as np
import multiprocessing as mp

from qiskit_helper_functions.non_ibmq_functions import generate_circ, read_dict

from cutqc.main import CutQC
from cutqc.helper_fun import get_dirname

if __name__ == '__main__':
    # To run on IBM devices, enter your IBMQ account information here
    ibmq = {'token':'',
            'hub':'',
            'group':'',
            'project':''}

    # Generate some test circuits
    circuits = {}
    circuit_cases = []
    max_subcircuit_qubit = 5
    circuit_type = 'supremacy'
    full_circ_size = 6
    circuit_name = '%s_%d'%(circuit_type,full_circ_size)
    circuit = generate_circ(full_circ_size=full_circ_size,circuit_type=circuit_type)
    circuits[circuit_name] = circuit
    circuit_cases.append('%s|%d'%(circuit_name,max_subcircuit_qubit))

    # Use CutQC package to evaluate the circuits
    num_threads = 1
    qubit_limit = 10
    eval_mode = 'ibmq_santiago'
    cutqc = CutQC(verbose=False)
    cutqc.cut(circuits=circuits,max_subcircuit_qubit=max_subcircuit_qubit,num_subcircuits=[2,3],max_cuts=10)
    cutqc.evaluate(circuit_cases=circuit_cases,eval_mode=eval_mode,num_nodes=1,num_threads=4,early_termination=[1],ibmq=ibmq)
    cutqc.post_process(circuit_cases=circuit_cases,eval_mode=eval_mode,num_nodes=1,num_threads=num_threads,early_termination=1,qubit_limit=qubit_limit,recursion_depth=1)
    cutqc.verify(circuit_cases=circuit_cases,early_termination=1,num_threads=num_threads,qubit_limit=qubit_limit,eval_mode=eval_mode)