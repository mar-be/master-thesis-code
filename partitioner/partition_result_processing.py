import os
from os import write
from queue import Queue
from threading import Thread
from typing import Dict

import numpy as np
from cutqc.evaluator import mutate_measurement_basis
from cutqc.helper_fun import get_dirname
from qiskit_helper_functions.conversions import dict_to_array
from quantum_job import QuantumJob


class PartitionResultProcessing(Thread):

    def __init__(self, input:Queue, partition_dict:Dict, force_prob:bool=True) -> None:
        self._input = input
        self._partition_dict = partition_dict
        self._force_prob = force_prob
        Thread.__init__(self)

    def run(self) -> None:
        print("Started PartitionResultProcessing")
        while True:
            job = self._input.get()
            print(f"Got job with id {job.id}")
            self.write(job)

    def _get_prob_dist(self, job:QuantumJob) -> np.ndarray:
        counts = job.result.get_counts()
        return dict_to_array(counts, self._force_prob)

    def write(self, job):
        subcircuit_idx, inits, meas = job.key
        cut_solution = self._partition_dict[job.parent]["cut_solution"]
        all_indexed_combinations = self._partition_dict[job.parent]["all_indexed_combinations"]

        max_subcircuit_qubit = cut_solution['max_subcircuit_qubit']
        counter = cut_solution['counter']

        eval_folder = get_dirname(circuit_name=job.parent,max_subcircuit_qubit=max_subcircuit_qubit,
            early_termination=None,num_threads=None,eval_mode="ibmq",qubit_limit=None,field='evaluator')
        if not os.path.exists(eval_folder):
            os.makedirs(eval_folder)    

        subcircuit_inst_prob = self._get_prob_dist(job)

        mutated_meas = mutate_measurement_basis(meas)
        for meas in mutated_meas:
            index = all_indexed_combinations[subcircuit_idx][(tuple(inits),tuple(meas))]
            eval_file_name = '%s/raw_%d_%d.txt'%(eval_folder,subcircuit_idx,index)
            eval_file = open(eval_file_name,'w')
            eval_file.write('d=%d effective=%d\n'%(counter[subcircuit_idx]['d'],counter[subcircuit_idx]['effective']))
            [eval_file.write('%s '%x) for x in inits]
            eval_file.write('\n')
            [eval_file.write('%s '%x) for x in meas]
            eval_file.write('\n')
            [eval_file.write('%e '%x) for x in subcircuit_inst_prob] if type(subcircuit_inst_prob)==np.ndarray else eval_file.write('%e '%subcircuit_inst_prob)
            eval_file.close()
