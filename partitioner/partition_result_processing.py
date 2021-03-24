import glob
import os
import pickle
import shutil
import subprocess
import time
from os import write
from queue import Queue
from threading import Thread
from typing import Dict

import logger
import numpy as np
from cutqc.distributor import distribute
from cutqc.evaluator import mutate_measurement_basis
from cutqc.helper_fun import get_dirname
from cutqc.post_process import build, get_combinations
from qiskit.result.models import ExperimentResult, ExperimentResultData
from qiskit.result.result import Result
from qiskit_helper_functions.conversions import dict_to_array
from qiskit_helper_functions.non_ibmq_functions import find_process_jobs
from quantum_job import Modification_Type, QuantumJob


class ResultWriter(Thread):

    def __init__(self, input:Queue, completed_jobs:Queue, partition_dict:Dict, force_prob:bool=True) -> None:
        self._log = logger.get_logger(type(self).__name__)
        self._input = input
        self._completed_jobs = completed_jobs
        self._partition_dict = partition_dict
        self._force_prob = force_prob
        self._result_count = {}
        Thread.__init__(self)

    def run(self) -> None:
        self._log.info("Started ResultWriter")
        while True:
            job = self._input.get()
            self._log.debug(f"Got job with id {job.id}")
            self._write(job)
            if self._results_complete(job):
                self._log.info(f"All results are available for job {job.parent}")
                self._completed_jobs.put(self._partition_dict[job.parent]["job"])

    def _results_complete(self, job:QuantumJob):
        parent_id = job.parent
        try: 
            self._result_count[parent_id] += 1
        except KeyError:
            self._result_count[parent_id] = 1
        if self._partition_dict[parent_id]["num_sub_jobs"] == self._result_count[parent_id]:
            self._result_count.pop(parent_id)
            self._partition_dict[parent_id]["result_dict"] = job.result.to_dict()
            return True
        return False
        
        

    def _get_prob_dist(self, job:QuantumJob) -> np.ndarray:
        counts = job.result.get_counts()
        return dict_to_array(counts, self._force_prob)

    def _write(self, job:QuantumJob):
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


class ResultProcessing(Thread):

    def __init__(self, input:Queue, output:Queue, partition_dict:Dict, verbose=False) -> None:
        self._log = logger.get_logger(type(self).__name__)
        self._input = input
        self._output = output
        self._partition_dict = partition_dict
        self._verbose = verbose
        Thread.__init__(self)

    def run(self) -> None:
        eval_mode = "ibmq"
        num_threads = 4
        early_termination = 1
        qubit_limit = 10
        recursion_depth = 1
        while True:
            job = self._input.get()
            self._log.info(f"Postprocess job {job.id}")
            self._measure(job, eval_mode, num_threads)
            self._organize(job, eval_mode, num_threads)
            self._vertical_collapse(job, early_termination, eval_mode)
            self._write_all_files(job, eval_mode)
            reconstructed_prob = self.post_process(job, eval_mode, num_threads, early_termination, qubit_limit, recursion_depth)
            job.result_prob = self._createResult(job, reconstructed_prob)
            job.type = Modification_Type.partition
            self._output.put(job)
            self.verify(job, early_termination, num_threads, qubit_limit, eval_mode)
            self._partition_dict.pop(job.id)
            self._clean_all_files(job)

    def _write_all_files(self, job, eval_mode):

        circuit_name = job.id
        cut_solution = self._partition_dict[job.id]["cut_solution"]
        max_subcircuit_qubit = cut_solution['max_subcircuit_qubit']

        source_folder = get_dirname(circuit_name=circuit_name,max_subcircuit_qubit=max_subcircuit_qubit,
        early_termination=None,eval_mode=None,num_threads=None,qubit_limit=None,field='cutter')
        if not os.path.exists(source_folder):
            os.makedirs(source_folder)
        pickle.dump(cut_solution, open('%s/subcircuits.pckl'%(source_folder),'wb'))

        eval_folder = get_dirname(circuit_name=circuit_name,max_subcircuit_qubit=max_subcircuit_qubit,
        early_termination=None,num_threads=None,eval_mode=eval_mode,qubit_limit=None,field='evaluator')
        if not os.path.exists(eval_folder):
            os.makedirs(eval_folder)

        all_indexed_combinations = self._partition_dict[job.id]["all_indexed_combinations"]
        pickle.dump(all_indexed_combinations, open('%s/all_indexed_combinations.pckl'%(eval_folder),'wb'))

    def _clean_all_files(self, job):
        dirname = f'./cutqc_data/{job.id}'
        shutil.rmtree(dirname)

    def _measure(self, job, eval_mode, num_threads):
        subprocess.run(['rm','./cutqc/measure'])
        subprocess.run(['icc','./cutqc/measure.c','-o','./cutqc/measure','-lm'])

       
        cut_solution = self._partition_dict[job.id]["cut_solution"]
        max_subcircuit_qubit = cut_solution['max_subcircuit_qubit']
        full_circuit = cut_solution['circuit']
        subcircuits = cut_solution['subcircuits']

        eval_folder = get_dirname(circuit_name=job.id,max_subcircuit_qubit=max_subcircuit_qubit,
        early_termination=None,num_threads=None,eval_mode=eval_mode, qubit_limit=None,field='evaluator')
        for subcircuit_idx in range(len(subcircuits)):
            eval_files = glob.glob('%s/raw_%d_*.txt'%(eval_folder,subcircuit_idx))
            child_processes = []
            for rank in range(num_threads):
                process_eval_files = find_process_jobs(jobs=range(len(eval_files)),rank=rank,num_workers=num_threads)
                process_eval_files = [str(x) for x in process_eval_files]
                if rank==0 and self._verbose:
                    self._log.debug('%s subcircuit %d : rank %d/%d needs to measure %d/%d instances'%(
                        job.id,subcircuit_idx,rank,num_threads,len(process_eval_files),len(eval_files)))
                p = subprocess.Popen(args=['./cutqc/measure', '%d'%rank, eval_folder, eval_mode,
                '%d'%full_circuit.num_qubits,'%d'%subcircuit_idx, '%d'%len(process_eval_files), *process_eval_files])
                child_processes.append(p)
            [cp.wait() for cp in child_processes]

    def _organize(self, job, eval_mode, num_threads):
        '''
        Organize parallel processing for the subsequent vertical collapse procedure
        '''
        cut_solution = self._partition_dict[job.id]["cut_solution"]
        max_subcircuit_qubit = cut_solution['max_subcircuit_qubit']
        full_circuit = cut_solution['circuit']
        subcircuits = cut_solution['subcircuits']
        complete_path_map = cut_solution['complete_path_map']
        counter = cut_solution['counter']

        eval_folder = get_dirname(circuit_name=job.id,max_subcircuit_qubit=max_subcircuit_qubit,
        early_termination=None,num_threads=None,eval_mode=eval_mode,qubit_limit=None,field='evaluator')

        all_indexed_combinations = self._partition_dict[job.id]["all_indexed_combinations"]
        O_rho_pairs, combinations = get_combinations(complete_path_map=complete_path_map)
        kronecker_terms, _ = build(full_circuit=full_circuit, combinations=combinations,
        O_rho_pairs=O_rho_pairs, subcircuits=subcircuits, all_indexed_combinations=all_indexed_combinations)

        for rank in range(num_threads):
            subcircuit_kron_terms_file = open('%s/subcircuit_kron_terms_%d.txt'%(eval_folder,rank),'w')
            subcircuit_kron_terms_file.write('%d subcircuits\n'%len(kronecker_terms))
            for subcircuit_idx in kronecker_terms:
                if eval_mode=='runtime':
                    rank_subcircuit_kron_terms = [list(kronecker_terms[subcircuit_idx].keys())[0]]
                else:
                    rank_subcircuit_kron_terms = find_process_jobs(jobs=list(kronecker_terms[subcircuit_idx].keys()),rank=rank,num_workers=num_threads)
                subcircuit_kron_terms_file.write('subcircuit %d kron_terms %d num_effective %d\n'%(
                    subcircuit_idx,len(rank_subcircuit_kron_terms),counter[subcircuit_idx]['effective']))
                for subcircuit_kron_term in rank_subcircuit_kron_terms:
                    subcircuit_kron_terms_file.write('subcircuit_kron_index=%d kron_term_len=%d\n'%(kronecker_terms[subcircuit_idx][subcircuit_kron_term],len(subcircuit_kron_term)))
                    if eval_mode=='runtime':
                        [subcircuit_kron_terms_file.write('%d,0 '%(x[0])) for x in subcircuit_kron_term]
                    else:
                        [subcircuit_kron_terms_file.write('%d,%d '%(x[0],x[1])) for x in subcircuit_kron_term]
                    subcircuit_kron_terms_file.write('\n')
                if rank==0:
                    self._log.debug('%s subcircuit %d : rank %d/%d needs to vertical collapse %d/%d instances'%(
                        job.id,subcircuit_idx,rank,num_threads,len(rank_subcircuit_kron_terms),len(kronecker_terms[subcircuit_idx])))
            subcircuit_kron_terms_file.close()
    
    def _vertical_collapse(self, job, early_termination, eval_mode):
        subprocess.run(['rm','./cutqc/vertical_collapse'])
        subprocess.run(['icc','-mkl','./cutqc/vertical_collapse.c','-o','./cutqc/vertical_collapse','-lm'])

        
        cut_solution = self._partition_dict[job.id]["cut_solution"]
        max_subcircuit_qubit = cut_solution['max_subcircuit_qubit']
        full_circuit = cut_solution['circuit']
        subcircuits = cut_solution['subcircuits']
        complete_path_map = cut_solution['complete_path_map']
        counter = cut_solution['counter']

        eval_folder = get_dirname(circuit_name=job.id,max_subcircuit_qubit=max_subcircuit_qubit,
        early_termination=None,num_threads=None,eval_mode=eval_mode,qubit_limit=None,field='evaluator')
        vertical_collapse_folder = get_dirname(circuit_name=job.id,max_subcircuit_qubit=max_subcircuit_qubit,
        early_termination=early_termination,num_threads=None,eval_mode=eval_mode,qubit_limit=None,field='vertical_collapse')

        rank_files = glob.glob('%s/subcircuit_kron_terms_*.txt'%eval_folder)
        if len(rank_files)==0:
            raise Exception('There are no rank_files for _vertical_collapse')
        if os.path.exists(vertical_collapse_folder):
            subprocess.run(['rm','-r',vertical_collapse_folder])
        os.makedirs(vertical_collapse_folder)
        child_processes = []
        for rank in range(len(rank_files)):
            subcircuit_kron_terms_file = '%s/subcircuit_kron_terms_%d.txt'%(eval_folder,rank)
            p = subprocess.Popen(args=['./cutqc/vertical_collapse', '%d'%full_circuit.num_qubits, '%s'%subcircuit_kron_terms_file,
            '%s'%eval_folder, '%s'%vertical_collapse_folder, '%d'%early_termination, '%d'%rank, '%s'%eval_mode])
            child_processes.append(p)
        [cp.wait() for cp in child_processes]
        if early_termination==1:
            measured_files = glob.glob('%s/measured*.txt'%eval_folder)
            [subprocess.run(['rm',measured_file]) for measured_file in measured_files]
            [subprocess.run(['rm','%s/subcircuit_kron_terms_%d.txt'%(eval_folder,rank)]) for rank in range(len(rank_files))]

    
    def post_process(self,job,eval_mode,num_threads,early_termination,qubit_limit,recursion_depth):
        self._log.debug('Postprocess, job = %s'%job.id)
        subprocess.run(['rm','./cutqc/merge'])
        subprocess.run(['icc','-mkl','./cutqc/merge.c','-o','./cutqc/merge','-lm'])
        subprocess.run(['rm','./cutqc/build'])
        subprocess.run(['icc','-fopenmp','-mkl','-lpthread','-march=native','./cutqc/build.c','-o','./cutqc/build','-lm'])

        circuit_name = job.id
        cut_solution = self._partition_dict[job.id]["cut_solution"]
        max_subcircuit_qubit = cut_solution['max_subcircuit_qubit']
        full_circuit = cut_solution['circuit']
        subcircuits = cut_solution['subcircuits']
        complete_path_map = cut_solution['complete_path_map']
        counter = cut_solution['counter']

        circuit_case = '%s|%d'%(circuit_name,max_subcircuit_qubit)

        dest_folder = get_dirname(circuit_name=circuit_name,max_subcircuit_qubit=max_subcircuit_qubit,
        early_termination=early_termination,num_threads=num_threads,eval_mode=eval_mode,qubit_limit=qubit_limit,field='build')

        if os.path.exists('%s'%dest_folder):
            subprocess.run(['rm','-r',dest_folder])
        os.makedirs(dest_folder)

        vertical_collapse_folder = get_dirname(circuit_name=circuit_name,max_subcircuit_qubit=max_subcircuit_qubit,
        early_termination=early_termination,num_threads=None,eval_mode=eval_mode,qubit_limit=None,field='vertical_collapse')

        reconstructed_prob = None
        for recursion_layer in range(recursion_depth):
      
            self._log.debug('*'*20 + '%s Recursion Layer %d'%(circuit_case,recursion_layer) + '*'*20)
            recursion_qubit = qubit_limit
            self._log.debug('__Distribute__')
            distribute(circuit_name=circuit_name,max_subcircuit_qubit=max_subcircuit_qubit,
            eval_mode=eval_mode,early_termination=early_termination,num_threads=num_threads,qubit_limit=qubit_limit,
            recursion_layer=recursion_layer,recursion_qubit=recursion_qubit,verbose=self._verbose)
            self._log.debug('__Merge__')
            terminated = self._merge(circuit_case=circuit_case,vertical_collapse_folder=vertical_collapse_folder,dest_folder=dest_folder,
            recursion_layer=recursion_layer,eval_mode=eval_mode)
            if terminated:
                break
            self._log.debug('__Build__')
            reconstructed_prob = self._build(circuit_case=circuit_case,dest_folder=dest_folder,recursion_layer=recursion_layer,eval_mode=eval_mode)
        return reconstructed_prob

    def _merge(self, circuit_case, dest_folder, recursion_layer, vertical_collapse_folder, eval_mode):
        dynamic_definition_folder = '%s/dynamic_definition_%d'%(dest_folder,recursion_layer)
        if not os.path.exists(dynamic_definition_folder):
            return True
        merge_files = glob.glob('%s/merge_*.txt'%dynamic_definition_folder)
        num_threads = len(merge_files)
        child_processes = []
        rank = None
        for rank in range(num_threads):
            merge_file = '%s/merge_%d.txt'%(dynamic_definition_folder,rank)
            p = subprocess.Popen(args=['./cutqc/merge', '%s'%merge_file, '%s'%vertical_collapse_folder, '%s'%dynamic_definition_folder,
            '%d'%rank, '%d'%recursion_layer, '%s'%eval_mode])
            child_processes.append(p)
        elapsed = 0
        for rank in range(num_threads):
            cp = child_processes[rank]
            cp.wait()
        time.sleep(1)
        if rank == None:
            raise UnboundLocalError
        rank_logs = open('%s/rank_%d_summary.txt'%(dynamic_definition_folder,rank), 'r')
        lines = rank_logs.readlines()
        assert lines[-2].split(' = ')[0]=='Total merge time' and lines[-1]=='DONE'
        elapsed = max(elapsed,float(lines[-2].split(' = ')[1]))

        self._log.debug('%s _merge took %.3e seconds'%(circuit_case,elapsed))
        # pickle.dump({'merge_time_%d'%recursion_layer:elapsed}, open('%s/summary.pckl'%(dest_folder),'ab'))
        return False
    
    def _build(self, circuit_case, dest_folder, recursion_layer, eval_mode):
        dynamic_definition_folder = '%s/dynamic_definition_%d'%(dest_folder,recursion_layer)
        build_files = glob.glob('%s/build_*.txt'%dynamic_definition_folder)
        num_threads = len(build_files)
        child_processes = []
        for rank in range(num_threads):
            build_file = '%s/build_%d.txt'%(dynamic_definition_folder,rank)
            p = subprocess.Popen(args=['./cutqc/build', '%s'%build_file, '%s'%dynamic_definition_folder, 
            '%s'%dynamic_definition_folder, '%d'%rank, '%d'%recursion_layer, '%s'%eval_mode])
            child_processes.append(p)
        
        elapsed = []
        reconstructed_prob = None
        for rank in range(num_threads):
            cp = child_processes[rank]
            cp.wait()
            rank_logs = open('%s/rank_%d_summary.txt'%(dynamic_definition_folder,rank), 'r')
            lines = rank_logs.readlines()
            assert lines[-2].split(' = ')[0]=='Total build time' and lines[-1] == 'DONE'
            elapsed.append(float(lines[-2].split(' = ')[1]))

            fp = open('%s/reconstructed_prob_%d.txt'%(dynamic_definition_folder,rank), 'r')
            rank_reconstructed_prob = None
            for i, line in enumerate(fp):
                rank_reconstructed_prob = line.split(' ')[:-1]
                rank_reconstructed_prob = np.array(rank_reconstructed_prob)
                rank_reconstructed_prob = rank_reconstructed_prob.astype(np.float)
                if i>0:
                    raise Exception('C build_output should not have more than 1 line')
            fp.close()
            subprocess.run(['rm','%s/reconstructed_prob_%d.txt'%(dynamic_definition_folder,rank)])
            try:
                if rank_reconstructed_prob == None:
                    raise UnboundLocalError
            except ValueError:
                pass
            if isinstance(reconstructed_prob,np.ndarray):
                reconstructed_prob += rank_reconstructed_prob
            else:
                reconstructed_prob = rank_reconstructed_prob
        elapsed = np.array(elapsed)
        self._log.debug('%s _build took %.3e seconds'%(circuit_case,np.mean(elapsed)))
        pickle.dump({'build_times_%d'%recursion_layer:np.array(elapsed),'build_time_%d'%recursion_layer:np.mean(elapsed)}, open('%s/summary.pckl'%(dest_folder),'ab'))
        max_states = sorted(range(len(reconstructed_prob)),key=lambda x:reconstructed_prob[x],reverse=True)
        pickle.dump({'zoomed_ctr':0,'max_states':max_states,'reconstructed_prob':reconstructed_prob},open('%s/build_output.pckl'%(dynamic_definition_folder),'wb'))
        return reconstructed_prob

    def _createResult(self, job: QuantumJob, prob: np.ndarray) -> Result:
        prob_dict = {}
        for i, p in enumerate(prob):
            if p != 0:
                prob_dict[hex(i)] = p
        return prob_dict

    def verify(self, job, early_termination, num_threads, qubit_limit, eval_mode):
        circuit_name = job.id
        max_subcircuit_qubit = self._partition_dict[job.id]["cut_solution"]['max_subcircuit_qubit']
        subprocess.run(['python','-m','cutqc.verify',
        '--circuit_name',circuit_name,
        '--max_subcircuit_qubit',str(max_subcircuit_qubit),
        '--early_termination',str(early_termination),
        '--num_threads',str(num_threads),
        '--qubit_limit',str(qubit_limit),
        '--eval_mode',eval_mode])
