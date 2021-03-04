# Import the RB Functions
from logging import Logger
from typing import Dict
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


def evaluate(rb_fit:RBFitter, rb_opts:Dict, result_queue:Queue, name:str, log:Logger):
    for rb_seed in range(rb_opts['nseeds']):
        results = []
        for _ in range(len(rb_opts['length_vector'])):
            job = result_queue.get()
            results.append(job.result)
        rb_fit.add_data(results)
        log.info('After seed %d, alpha: %f, EPC: %f'%(rb_seed,rb_fit.fit[0]['params'][1], rb_fit.fit[0]['epc']))
        

    plt.figure(figsize=(8, 6))
    ax = plt.subplot(1, 1, 1)

    # Plot the essence by calling plot_rb_data
    rb_fit.plot_rb_data(0, ax=ax, add_label=True, show_plt=False)
        
    # Add title and label
    ax.set_title('%d Qubit RB - NO Aggregation'%(nQ), fontsize=18)

    plt.savefig(name + ".png")
    log.info("Saved file " + name)


if __name__ == "__main__":

    log = get_logger("Evaluate")
    # Generate RB circuits (2Q RB)

    # number of qubits
    nQ = 2 
    rb_opts = {}
    #Number of Cliffords in the sequence
    rb_opts['length_vector'] = [1, 10, 20, 50, 75, 100, 125, 150, 175, 200]
    # Number of seeds (random sequences)
    rb_opts['nseeds'] = 10
    # Default pattern
    rb_opts['rb_pattern'] = [[0, 1]]

    rb_circs, xdata = rb.randomized_benchmarking_seq(**rb_opts)

    shots = 8192
    backend_name = "ibmq_quito"
    # backend_name = "ibmq_qasm_simulator"

    count = 0
    for listElem in rb_circs:
        count += len(listElem)      

    log.info(f"Generated {count} circuits")

    


    provider = IBMQ.load_account()
    backend = provider.get_backend(backend_name)
    backend_data = Backend_Data(backend)

    input_pipeline = Queue()
    input_exec = Queue()
    output_exec = Queue()
    agg_results = Queue()
    output_pipline = Queue()

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


    rb_fit = rb.RBFitter(None, xdata, rb_opts['rb_pattern'])
    rb_agg_fit = rb.RBFitter(None, xdata, rb_opts['rb_pattern'])

    evaluate(rb_fit, rb_opts, output_pipline, backend_name+"no_aggregation", log)
    evaluate(rb_agg_fit, rb_opts, output_pipline, backend_name+"aggregation", log)
