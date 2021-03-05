# Import the RB Functions
from datetime import datetime
from logging import Logger
import os
from typing import Dict, List
from qiskit.ignis.verification.randomized_benchmarking.fitters import RBFitter
from analyzer.backend_chooser import Backend_Data
from quantum_job import QuantumJob
from logger import get_logger
from queue import Queue
from analyzer.result_analyzer import ResultAnalyzer
from execution_handler.execution_handler import ExecutionHandler
from aggregator.aggregator import Aggregator, AggregatorResults
import qiskit.ignis.verification.randomized_benchmarking as rb
from qiskit import IBMQ
import matplotlib.pyplot as plt
from qiskit.result import Result

def evaluate(results:List[Result], rb_opts:Dict, xdata:List, dir_path, backend_name:str, log:Logger):
    half = len(results)//2
    no_agg_results = results[:half] 
    agg_results = results[half:]
    assert(len(no_agg_results)==len(agg_results))

    dir_path_backend = f"{dir_path}/{backend_name}"
    os.mkdir(dir_path_backend)

    no_agg_fit = fit(no_agg_results, rb_opts, xdata, log)
    plot(no_agg_fit, f"{backend_name} no agg", f"{dir_path_backend}/no_aggregation.png", log)
    agg_fit = fit(agg_results, rb_opts, xdata, log)
    plot(agg_fit, f"{backend_name} agg", f"{dir_path_backend}/aggregation.png", log)
    
        

    

def fit(results:List[Result], rb_opts:Dict, xdata:List, log:Logger) -> RBFitter:
    rb_fit = rb.RBFitter(None, xdata, rb_opts['rb_pattern'])
    batch_size = len(rb_opts['length_vector'])
    for rb_seed in range(rb_opts['nseeds']):
        result_batch = results[rb_seed*batch_size: rb_seed*batch_size + batch_size]
        rb_fit.add_data(result_batch)
        log.info('After seed %d, alpha: %f, EPC: %f'%(rb_seed,rb_fit.fit[0]['params'][1], rb_fit.fit[0]['epc']))
    return rb_fit


def plot(rb_fit:RBFitter, name:str, filename:str, log:Logger):
    plt.figure(figsize=(8, 6))
    ax = plt.subplot(1, 1, 1)

    # Plot the essence by calling plot_rb_data
    rb_fit.plot_rb_data(0, ax=ax, add_label=True, show_plt=False)
        
    # Add title and label
    ax.set_title('%d Qubit RB - %s'%(nQ, name), fontsize=18)

    plt.savefig(filename)
    log.info("Saved file " + filename)

if __name__ == "__main__":

    log = get_logger("Evaluate")
    # Generate RB circuits (2Q RB)
    
    dir_path = "./rb_data"

    # number of qubits
    nQ = 2 
    rb_opts = {}
    #Number of Cliffords in the sequence
    rb_opts['length_vector'] = [1, 10, 20, 50, 75, 100, 125, 150, 175, 200]
    # Number of seeds (random sequences)
    rb_opts['nseeds'] = 10
    # Default pattern
    rb_opts['rb_pattern'] = [[0, 1]]


    shots = 8192

    backend_names = ['ibmq_qasm_simulator' , 'ibmq_athens', 'ibmq_santiago', 'ibmq_quito', 'ibmq_lima', 'ibmq_belem']
    # backend_names = ['ibmq_qasm_simulator']

    rb_circs, xdata = rb.randomized_benchmarking_seq(**rb_opts)

    count = 0
    for listElem in rb_circs:
        count += len(listElem)      

    log.info(f"Generated {count} circuits")

    provider = IBMQ.load_account()

   
    input_pipeline = Queue()
    input_exec = Queue()
    output_exec = Queue()
    agg_results = Queue()
    output_pipline = Queue()

    

    backend_data_list = []
    backends = {}
    for backend_name in backend_names:
        backend = provider.get_backend(backend_name)
        backend_data = Backend_Data(backend)
        backend_data_list.append(backend_data)
        backends[backend_name] = {"backend":backend, "backend_data":backend_data}

    for backend_data in backend_data_list:
        for rb_seed, rb_circ_seed in enumerate(rb_circs):
            for circ in rb_circ_seed:
                input_pipeline.put(QuantumJob(circuit=circ, shots=shots, backend_data=backend_data))
                input_exec.put(QuantumJob(circuit=circ, shots=shots, backend_data=backend_data))



    agg_job_dict = {}

    aggregator = Aggregator(input=input_pipeline, output=input_exec, job_dict=agg_job_dict, timeout=10)
    aggregator.start()

    exec_handler = ExecutionHandler(provider, input=input_exec, output=output_exec)
    exec_handler.start()

    result_analyzer = ResultAnalyzer(input=output_exec, output=output_pipline, output_agg=agg_results, output_part=None)
    result_analyzer.start()

    aggregator_results = AggregatorResults(input=agg_results, output=output_pipline, job_dict=agg_job_dict)
    aggregator_results.start()

    log.info("Started the Aggrgator pipeline")

    n_results = 2*rb_opts['nseeds']*len(rb_opts['length_vector'])*len(backend_names)
    results = {}
    for backend_name in backend_names:
        results[backend_name] = []

    try:
        os.makedirs(dir_path)
        print(f"Created directory {dir_path}")
    except FileExistsError:
        print(f"Directory {dir_path} already exists")

    now = datetime.now()
    now_str = now.strftime('%Y-%m-%d-%H-%M-%S')
    dir_path = f"{dir_path}/{now_str}"

    os.mkdir(dir_path)

    for i in range(n_results):
        job = output_pipline.get()
        r = job.result
        backend_name = job.backend_data.name
        log.debug(f"{i}: Got job {job.id},type {job.type}, from backend {backend_name}, success: {r.success}")
        results[backend_name].append(r)
        if len(results[backend_name]) == 2*rb_opts['nseeds']*len(rb_opts['length_vector']):
            evaluate(results.pop(backend_name), rb_opts, xdata, dir_path, backend_name, log)

