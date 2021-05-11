# Import the RB Functions
from datetime import datetime
from logging import Logger
import os
from typing import Any, Dict, List
from qiskit.circuit.quantumcircuit import QuantumCircuit
from qiskit.ignis.verification.randomized_benchmarking.fitters import RBFitter
from analyzer.backend_chooser import Backend_Data
from quantum_job import Execution_Type, QuantumJob
from logger import get_logger
from queue import Queue
from analyzer.result_analyzer import ResultAnalyzer
from execution_handler.execution_handler import ExecutionHandler
from aggregator.aggregator import Aggregator, AggregatorResults
import qiskit.ignis.verification.randomized_benchmarking as rb
from qiskit import IBMQ
import matplotlib.pyplot as plt
from qiskit.result import Result
import pickle
from threading import Timer

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
    

def pickle_dump(object, filename):
    with open(filename,'wb') as f:
        pickle.dump(object, f)

def pickle_load(filename:str) -> Any:
    with open(filename,'rb') as f:
        return pickle.load(f)

def pickle_append_result(result:Result, filename):
    if os.path.exists(filename):
        results = pickle_load(filename)
        results.append(result)
    else:
        results = [result]
    pickle_dump(results, filename)



def store_backend_data(backend_dict:Dict, dir_path:str, backend_name:str, log:Logger):
    path = f"{dir_path}/{backend_name}/data"
    os.makedirs(path)
    pickle_dump(backend_dict, f"{path}/backend_dict.pkl")
    log.info(f"Pickled backend_dict for backend {backend_name}")

def store_general_data(rb_circs:List[List[QuantumCircuit]], rb_opts:Dict, xdata:List,  dir_path:str, log:Logger):
    path = f"{dir_path}/general_data"
    os.mkdir(path)
    pickle_dump(rb_circs, f"{path}/rb_circs.pkl")
    pickle_dump(rb_opts, f"{path}/rb_opts.pkl")
    pickle_dump(xdata, f"{path}/xdata.pkl")
    log.info("Pickeld all general files")

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

    different_length = True
    delay_time_different_length = 60*1 

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

    # backend_names = ['ibmq_qasm_simulator' , 'ibmq_athens', 'ibmq_santiago', 'ibmq_quito', 'ibmq_lima', 'ibmq_belem']
    backend_names = ['ibmq_qasm_simulator']

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
        for length_idx in range(len(rb_opts['length_vector'])):
            for rb_seed, rb_circ_seed in enumerate(rb_circs):
                circ = rb_circ_seed[length_idx]
                input_pipeline.put(QuantumJob(circuit=circ, shots=shots, backend_data=backend_data))
                input_exec.put(QuantumJob(circuit=circ, shots=shots, backend_data=backend_data))

    if different_length:
        log.info(f"delay differnt length circuit aggregation by {delay_time_different_length}s")
        def different_length_circuits():
            log.info(f"start differnt length circuit aggregation")
            for backend_data in backend_data_list:
                for rb_seed, rb_circ_seed in enumerate(rb_circs):
                    for circ in rb_circ_seed:
                        input_pipeline.put(QuantumJob(circuit=circ, shots=shots, backend_data=backend_data))
        
        Timer(delay_time_different_length, function=different_length_circuits).start()


    agg_job_dict = {}

    aggregator = Aggregator(input=input_pipeline, output=input_exec, job_dict=agg_job_dict, timeout=10)
    aggregator.start()

    exec_handler = ExecutionHandler(provider, input=input_exec, output=output_exec, batch_timeout=60, max_transpile_batch_size=float('inf'))
    exec_handler.start()

    result_analyzer = ResultAnalyzer(input=output_exec, output=output_pipline, output_agg=agg_results, output_part=None)
    result_analyzer.start()

    aggregator_results = AggregatorResults(input=agg_results, output=output_pipline, job_dict=agg_job_dict)
    aggregator_results.start()

    log.info("Started the Aggrgator pipeline")

    n_circuits = rb_opts['nseeds']*len(rb_opts['length_vector'])
    results_per_backend = 3*n_circuits if different_length else 2*n_circuits
    n_results = results_per_backend*len(backend_names)
    results_counter = {}
    for backend_name in backend_names:
        results_counter[backend_name] = 0

    try:
        os.makedirs(dir_path)
        print(f"Created directory {dir_path}")
    except FileExistsError:
        print(f"Directory {dir_path} already exists")

    now = datetime.now()
    now_str = now.strftime('%Y-%m-%d-%H-%M-%S')
    dir_path = f"{dir_path}/{now_str}"

    os.mkdir(dir_path)

    store_general_data(rb_circs, rb_opts, xdata, dir_path, log)


    for backend_name in backend_names:
        backend = backends[backend_name]["backend"]
        backend_dict = {"name":backend.name()}
        if backend.configuration() != None:
            backend_dict["config"] = backend.configuration().to_dict() 
        
        if backend.status() != None:
            backend_dict["status"] = backend.status().to_dict()

        if backend.properties() != None:
            backend_dict["properties"] = backend.properties().to_dict()
        store_backend_data(backend_dict, dir_path, backend_name, log)

        agg_path = f"{dir_path}/{backend_name}/data/res_agg"
        no_agg_path = f"{dir_path}/{backend_name}/data/res_no_agg"
        if different_length:
            agg_diff_path = f"{dir_path}/{backend_name}/data/res_agg_diff"
            os.mkdir(agg_diff_path)
        os.mkdir(agg_path)
        os.mkdir(no_agg_path)

    for i in range(n_results):
        job = output_pipline.get()
        r = job.result
        backend_name = job.backend_data.name
        if job.type == Execution_Type.aggregation:
            pickle_path = f"{dir_path}/{backend_name}/data/res_agg/{r._get_experiment(0).header.name}.pkl"
            if different_length and os.path.isfile(pickle_path):
                pickle_path = f"{dir_path}/{backend_name}/data/res_agg_diff/{r._get_experiment(0).header.name}.pkl"
        else:
            pickle_path = f"{dir_path}/{backend_name}/data/res_no_agg/{r._get_experiment(0).header.name}.pkl"
        pickle_dump(r, pickle_path)
        
        log.debug(f"{i}: Got result {r._get_experiment(0).header.name}, type {job.type}, from backend {backend_name}, success: {r.success}")
        results_counter[backend_name] += 1
        if results_counter[backend_name] == results_per_backend:
            log.info(f"Got all results for {backend_name}")

    log.info("Finished")

