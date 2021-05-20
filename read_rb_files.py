import itertools
import os
import pickle
from datetime import datetime
from logging import Logger
from typing import Any, Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from qiskit.circuit.quantumcircuit import QuantumCircuit
from qiskit.ignis.verification.randomized_benchmarking.fitters import RBFitter
from qiskit.result.result import Result

from evaluate.colors import BLUE_COLOR_LIST, GREEN_COLOR_LIST, RED_COLOR_LIST
from logger import get_logger
from randomized_benchmarking import store_general_data


def pickle_load(filename:str) -> Any:
    with open(filename,'rb') as f:
        return pickle.load(f)

def pickle_dump(object, filename):
    with open(filename,'wb') as f:
        pickle.dump(object, f)

def plot(no_agg_fit:RBFitter, agg_fit:RBFitter, path:str, title:str, log:Logger, no_agg_color:List = BLUE_COLOR_LIST, agg_color: List = RED_COLOR_LIST):
    """Create one diagram for the aggregated and non-aggregated RB dat

    Args:
        no_agg_fit (RBFitter): the fitter object for the non-aggregated data
        agg_fit (RBFitter): the fitter object for the aggregated data
        path (str): where to store the file
        title (str): of the plot
        log (Logger): logger object
        no_agg_color (List, optional): Colors for the non-aggregated data. Defaults to BLUE_COLOR_LIST.
        agg_color (List, optional): Colors for the non-aggregated data. Defaults to RED_COLOR_LIST.
    """
    plt.figure(figsize=(8, 6))
    ax = plt.subplot(1, 1, 1)

    ax = fitter_plot(agg_fit, "aggregation", ax, agg_color, x_shift=-1, mode="agg")
    ax = fitter_plot(no_agg_fit, "no aggregation", ax, no_agg_color, x_shift=1, mode="no agg")

    ax.tick_params(labelsize=16)
    ax.set_xlabel('Clifford Length (Circuit Depth)', fontsize=18)
    ax.set_ylabel('Fidelity', fontsize=18)
    ax.grid(True)
    ax.set_ylim([0.2,1])

    handles, labels = ax.get_legend_handles_labels()
    order = [0,1,2,3,4,5]
    #plt.legend([handles[idx] for idx in order],[labels[idx] for idx in order], fontsize=16)
    plt.legend(fontsize=16)
    
    plt.title(title, fontsize=18)
    plt.savefig(path, format="pdf", bbox_inches = 'tight')
    log.info(f"Created plot {path}")
        
def draw_violins(ax, data, positions, color, widths=12, alpha = 0.5, showmeans=False, mode="agg"):
    """Draw a half violin plot

    Args:
        ax ([type]): matplotlib axes
        data ([type]): y-data
        positions ([type]): x-data
        color ([type])
        widths (int, optional): of the violin. Defaults to 12.
        alpha (float, optional): opacity. Defaults to 0.5.
        showmeans (bool, optional): Indicate the mean value. Defaults to False.
        mode (str, optional): If "Agg", it draws violins to the left. Otherwise to the right. Defaults to "agg".
    """
    parts = ax.violinplot(data, positions=positions, widths=widths, showmeans=showmeans)

    for pc in parts['bodies']:
         # get the center
        m = np.mean(pc.get_paths()[0].vertices[:, 0])
        # modify the paths to not go further right than the center
        if mode == "agg":
            pc.get_paths()[0].vertices[:, 0] = np.clip(pc.get_paths()[0].vertices[:, 0], -np.inf, m)
        else:
            pc.get_paths()[0].vertices[:, 0] = np.clip(pc.get_paths()[0].vertices[:, 0], m, np.inf)
        pc.set_color(color[1])
        # pc.set_facecolor(color[0])
        # pc.set_edgecolor(color[1])

        
    if showmeans:
        parts['cmeans'].set_color(color[1])
    
    parts['cbars'].set_color(color[1])
    parts['cbars'].set_alpha(alpha)
    parts['cmins'].set_color(color[1])
    parts['cmins'].set_alpha(alpha)
    parts['cmaxes'].set_color(color[1])
    parts['cmaxes'].set_alpha(alpha)

def fitter_plot(rb_fit:RBFitter, name:str, ax:Axes, color:List, pattern_index=0, x_shift=0, mode="agg"):
    """Visualize the data for one RBFitter object.
    Draws the violins and the mean line.

    Args:
        rb_fit (RBFitter): RBFitter object conatining the data
        name (str): of the data
        ax (Axes): matplotlib axes to draw 
        color (List): color theme
        pattern_index (int, optional): Index of the data in the RBFitter object. Defaults to 0.
        x_shift (int, optional): apply a shift value to all x-values. Defaults to 0.
        mode (str, optional): Determines the direction of the violins. Defaults to "agg".

    Returns:
        [type]: [description]
    """
    
    fitted_func = rb_fit.rb_fit_fun
    xdata = rb_fit.cliff_lengths[pattern_index]
    raw_data = rb_fit.raw_data[pattern_index]
    ydata = rb_fit.ydata[pattern_index]
    fit = rb_fit.fit[pattern_index]

    raw_data_transposed = list(map(list, zip(*raw_data)))

    xdata_shift = xdata + x_shift

    x = list(itertools.chain.from_iterable(itertools.repeat(xdata_shift, len(raw_data))))
    y = list(itertools.chain.from_iterable(raw_data))

    #ax.plot(x, y, color=color[0], linestyle='none', marker='x', label=f"{name} data")
    
    draw_violins(ax, raw_data_transposed, xdata, color, mode=mode)
        
    # Plot the fit
    # ax.plot(xdata, fitted_func(xdata, *fit['params']), color=color[2], linestyle='-', linewidth=2, label=f"{name} fitted exponential")
    
    # Plot the std dev with error bars
    # ax.errorbar(xdata_shift, ydata['mean'], yerr=ydata['std'], color=color[0], linestyle='', linewidth=4, label=f"{name} std dev")

    # Plot the mean
    ax.plot(xdata, ydata['mean'], color=color[2], linestyle='-', linewidth=2, label=f"{name}")

    return ax

def fit_data(results:List[Result], rb_opts:Dict, xdata:List, log:Logger) -> RBFitter:
    """Create a RBFitter object from the data

    Args:
        results (List[Result]): evaluation results
        rb_opts (Dict): the configuration
        xdata (List): the sequences lengths 
        log (Logger): logger object

    Returns:
        RBFitter
    """
    rb_fit = RBFitter(None, xdata, rb_opts['rb_pattern'])
    rb_fit.add_data(results)
    rb_fit._nseeds = range(rb_opts["nseeds"])
    log.info(f"Fitted {len(results)} results, alpha: {rb_fit.fit[0]['params'][1]}, EPC: {rb_fit.fit[0]['epc']}")
    return rb_fit

def process_data(results:List[Result], rb_opts:Dict, xdata:List, backend_name:str, log:Logger) -> Tuple[RBFitter, RBFitter, int, int, int]:
    """Process the results and generate two RBFitter objects for the aggregated and non-aggregated data.

    Args:
        results (List[Result]): evaluation results
        rb_opts (Dict): the configuration
        xdata (List): the sequences lengths 
        backend_name (str)
        log (Logger): logger object

    Returns:
        Tuple[RBFitter, RBFitter, int, int, int]: non-aggregated RBFitter, aggregated RB-Fitter, number of different sequence lengths, number of qubits, number of evaluations per sequence length
    """
    half = len(results)//2
    no_agg_results = results[:half] 
    agg_results = results[half:]
    assert(len(no_agg_results)==len(agg_results))

    log.info(f"Fit no agg data for backend {backend_name}")
    no_agg_fit = fit_data(no_agg_results, rb_opts, xdata, log)
    log.info(f"Fit agg data for backend {backend_name}")
    agg_fit = fit_data(agg_results, rb_opts, xdata, log)
    n_sizes = len(rb_opts['length_vector'])
    n_qubits = results[0]._get_experiment(0).header.memory_slots
    return no_agg_fit, agg_fit, n_sizes, n_qubits, int(len(agg_results)/n_sizes)

def evaluate(results:List[Result], rb_opts:Dict, xdata:List, dir_path:str, backend_name:str, log:Logger):
    """Process the evaluation data and generate a plot for a backend

    Args:
        results (List[Result]): evaluation results
        rb_opts (Dict): the configuration
        xdata (List): the sequences lengths 
        dir_path (str): where to store the plot
        backend_name (str)
        log (Logger): logger object
    """
    no_agg_fit, agg_fit, n_sizes, n_qubits, n_circuits = process_data(results, rb_opts, xdata, backend_name, log)
    plot(no_agg_fit, agg_fit, f"{dir_path}/{backend_name}/{backend_name}_together.pdf", f"{n_qubits} Qubit RB {backend_name}: {n_circuits} circuits per length", log)
    

def get_general_data(path:str) -> Tuple[List[List[QuantumCircuit]], Dict, List[List[int]]]:
    """Get the general data of the evalution

    Args:
        path (str): path to the directory with all results

    Returns:
        Tuple[List[List[QuantumCircuit]], Dict, List[List[int]]]: the QuantumCircuits, the configuration of the RB evaluation, and the sequences lengths 
    """
    rb_circs = pickle_load(f"{path}/general_data/rb_circs.pkl")
    rb_opts = pickle_load(f"{path}/general_data/rb_opts.pkl")
    xdata = pickle_load(f"{path}/general_data/xdata.pkl")
    return rb_circs, rb_opts, xdata

def get_backend_data(path:str, backend_name:str)->Tuple[Dict, List[Result]]:
    """Get the stored data for a specific backend in the path

    Args:
        path (str):  path to the directory with all results
        backend_name (str): name of the specific backend. It has to coincide with a folder in the path


    Returns:
        Tuple[Dict, List[Result]]: Dict with information about the backend and a list of the results
    """
    backend_dict = pickle_load(f"{path}/{backend_name}/data/backend_dict.pkl")
    results = pickle_load(f"{path}/{backend_name}/data/results.pkl")
    return backend_dict, results
    
def evaluate_dir(path:str, log:Logger):
    """Evaluate a directory with RB results for multiple backends and generate the plots

    Args:
        path (str): path to the directory
        log (Logger): logger object
    """
    backend_names = get_backends_in_dir(path)
    for backend_name in backend_names:
        log.info(f"Evaluate backend {backend_name}")
        evaluate_files(path, backend_name, log)

def evaluate_files(path:str, backend_name:str, log:Logger):
    """Evaluate the RB results for a single backend and gererate a plot

    Args:
        path (str): path to the directory with all results
        backend_name (str): name of the specific backend. It has to coincide with a folder in the path
        log (Logger): logger object
    """
    rb_circs, rb_opts, xdata = get_general_data(path)
    backend_dict, results = get_backend_data(path, backend_name)
    evaluate(results, rb_opts, xdata, path, backend_name, log)

def get_backends_in_dir(path:str)-> List[str]:
    """Get all evaluated backends in the directory

    Args:
        path (str): to the directory

    Returns:
        List[str]: backend names
    """
    backend_names = []
    for (dirpath, dirnames, filenames) in os.walk(path):
        backend_names.extend(dirnames)
        break
    backend_names.remove("general_data")
    return backend_names


def all_backends_mean_graph(path:str, log:Logger):
    """Generates a graph that visualizes the mean gap between the aggregated and non-aggregated evaluation for all backends

    Args:
        path (str): directory with the evaluation results for all backends
        log (Logger): logger object
    """
    plt.figure(figsize=(8, 6))
    ax = plt.subplot(1, 1, 1)
    backend_names = get_backends_in_dir(path)
    for backend_name in backend_names:
        _, rb_opts, xdata = get_general_data(path)
        _, results = get_backend_data(path, backend_name)
        no_agg_fit, agg_fit, _, _, _ = process_data(results, rb_opts, xdata, backend_name, log)
        no_agg_mean = no_agg_fit.ydata[0]['mean']
        agg_mean = agg_fit.ydata[0]['mean']
        mean_diff = no_agg_mean-agg_mean
        x = agg_fit.cliff_lengths[0]
        ax.plot(x, mean_diff, linewidth=2, label=backend_name)
        log.info(f"Added {backend_name} to mean diff plot")
    ax.tick_params(labelsize=16)
    ax.set_xlabel('Clifford Length (Circuit Depth)', fontsize=18)
    ax.set_ylabel('Mean fidelity difference', fontsize=18)
    ax.grid(True)

    plt.legend(fontsize=16)
    
    plt.title("Fidelity gap between aggregated and non-aggregated \nexecution", fontsize=18)
    plt.savefig(f"{path}/mean_diff.pdf", format="pdf")



def check_or_init(var:Any, other_var:Any):
    """Checks if the variables are compatible. If var is None, it gets initialized
    """
    if not var is None:
        if isinstance(var, np.ndarray):
            if np.any(var != other_var):
                raise ValueError(f"{var} and {other_var} are not compatible")
        elif var != other_var:
            raise ValueError(f"{var} and {other_var} are not compatible")
    return other_var
    

def merge(dir_paths: List[str], result_path: str, log:Logger):
    """Merge the data from multiple evaluations

    Args:
        dir_paths (List[str]): list of directories to merge
        result_path (str): path of the merged directory
        log (Logger): logger object
    """
    rb_circs_merged = []
    nseeds_merged = 0
    xdata_merged = None
    results_merged = {}
    rb_opts_merged = None
    backends = {}
    for path in dir_paths:
        log.info(f"Get data for path {path}")
        rb_circs, rb_opts, xdata = get_general_data(path)
        rb_circs_merged.extend(rb_circs)
        nseeds_merged += rb_opts['nseeds']
        xdata_merged = check_or_init(xdata_merged, xdata)
        rb_opts_merged = check_or_init(rb_opts_merged, rb_opts)
        backend_names = get_backends_in_dir(path)
        for backend_name in backend_names:
            log.info(f"Get data for backend {backend_name} in path {path}")
            if not backend_name in results_merged.keys():
                results_merged[backend_name] = {"no_agg":[], "agg":[]}
            backend_dict, results = get_backend_data(path, backend_name)
            backends[backend_name] = backend_dict
            half = len(results)//2
            results_merged[backend_name]["no_agg"].extend(results[:half])
            results_merged[backend_name]["agg"].extend(results[half:])
            assert(len(results_merged[backend_name]["no_agg"])==len(results_merged[backend_name]["agg"]))

    try:
        os.makedirs(result_path)
        print(f"Created directory {result_path}")
    except FileExistsError:
        print(f"Directory {result_path} already exists")

    now = datetime.now()
    now_str = now.strftime('%Y-%m-%d-%H-%M-%S')
    result_path = f"{result_path}/{now_str}_merged_{len(dir_paths)}"
    os.mkdir(result_path)

    rb_opts_merged['nseeds'] = nseeds_merged

    store_general_data(results_merged, rb_opts_merged, xdata_merged, result_path, log)

    for backend_name, results in results_merged.items():
        backend_data_path = f"{result_path}/{backend_name}/data"
        os.makedirs(backend_data_path)
        backend_results = []
        backend_results.extend(generate_merged_result_names(results["no_agg"]))
        backend_results.extend(generate_merged_result_names(results["agg"]))
        pickle_dump(backend_results, f"{backend_data_path}/results.pkl")
        pickle_dump(backends[backend_name], f"{backend_data_path}/backend_dict.pkl")
        log.info(f"Pickeld all files for backend {backend_name}")

def generate_merged_result_names(results:List[Result]) -> List[Result]:
    """Rename the result names for the merged results

    Args:
        results (List[Result])

    Returns:
        List[Result]: renamed results
    """
    seed_counter = {}
    for result in results:
        name = result._get_experiment(0).header.name
        name_witout_seed = name.rsplit("_", 1)[0]
        if name_witout_seed in seed_counter.keys():
            seed_counter[name_witout_seed] += 1
            counter = seed_counter[name_witout_seed]
        else:
            seed_counter[name_witout_seed] = 0
            counter = 0
        result._get_experiment(0).header.name = name_witout_seed + "_" + str(counter)
    return results

def get_results_from_files(path:str) -> List[Result]:
    """Get the results from the disk

    Args:
        path (str): result directory

    Returns:
        List[Result]: list of the result objects
    """
    result_files = []
    for (dirpath, dirnames, filenames) in os.walk(path):
        result_files.extend(filenames)
    reverse_string_func = lambda s: s[::-1]
    result_files.sort(key=reverse_string_func)

    results = []

    for file in result_files:
        res = pickle_load(f"{path}/{file}")
        results.append(res)
    
    return results


def merge_separate_result_files(path:str, backend_name:str):
    """Merges the single files into one result file for a backend

    Args:
        path (str): evaluation directory
        backend_name (str)
    """
    no_agg_path = f"{path}/{backend_name}/data/res_no_agg"
    agg_path = f"{path}/{backend_name}/data/res_agg"
    
    no_agg_results = get_results_from_files(no_agg_path)
    agg_results = get_results_from_files(agg_path)

    results = []

    results.extend(no_agg_results)
    results.extend(agg_results)

    pickle_dump(results, f"{path}/{backend_name}/data/results.pkl")

    
def merge_separate_result_files_all_backends(path:str, log:Logger):
    """Merges the single files into one result file per backend


    Args:
        path (str): evaluation directory
        log (Logger): logger object
    """
    backends = get_backends_in_dir(path)
    for backend_name in backends:
        log.info(f"Merge results for backend {backend_name}")
        merge_separate_result_files(path, backend_name)

def evaluate_different_length_agg_dir(path:str, log:Logger):
    """Evaluate a RB directory for the different length evalution mode

    Args:
        path (str): evaluation directory
        log (Logger): logger object
    """
    backend_names = get_backends_in_dir(path)
    for backend_name in backend_names:
        log.info(f"Evaluate backend {backend_name}")
        evaluate_different_length_agg_files(path, backend_name, log)

def evaluate_different_length_agg_files(path:str, backend_name:str, log:Logger):
    """Evaluate a RB directory for the different length evalution mode for one backend

    Args:
        path (str): evaluation directory
        backend_name (str)
        log (Logger): logger object
    """
    rb_circs, rb_opts, xdata = get_general_data(path)
    backend_dict = pickle_load(f"{path}/{backend_name}/data/backend_dict.pkl")
    agg_path = f"{path}/{backend_name}/data/res_agg"
    no_agg_path = f"{path}/{backend_name}/data/res_no_agg"
    agg_diff_path = f"{path}/{backend_name}/data/res_agg_diff"
    no_agg_results = get_results_from_files(no_agg_path)
    agg_results = get_results_from_files(agg_path)
    agg_diff_results = get_results_from_files(agg_diff_path)
    no_agg_fit = fit_data(no_agg_results, rb_opts, xdata, log)
    agg_fit = fit_data(agg_results, rb_opts, xdata, log)
    agg_diff_fit = fit_data(agg_diff_results, rb_opts, xdata, log)
    n_sizes = len(rb_opts['length_vector'])
    n_circuits = int(len(agg_results)/n_sizes)
    n_qubits = no_agg_results[0]._get_experiment(0).header.memory_slots
    plot_different_length_agg(no_agg_fit, agg_fit, agg_diff_fit, f"{path}/{backend_name}/{backend_name}_diff_plot.pdf", f"{n_qubits} Qubit RB {backend_name}: {n_circuits} circuits per length")
    
def plot_different_length_agg(no_agg_fit:RBFitter, agg_fit:RBFitter, agg_diff_fit:RBFitter, path:str, title:str, no_agg_color: List = BLUE_COLOR_LIST, agg_color: List = RED_COLOR_LIST, agg_diff_color: List = GREEN_COLOR_LIST):
    """Generate a plot for the different length evalution mode for one backend

    Args:
        no_agg_fit (RBFitter): non-aggregated data
        agg_fit (RBFitter): aggregated data where circuits of the same lengths got aggregated
        agg_diff_fit (RBFitter): aggregated data where circuits of the different lengths got aggregated
        path (str): where to store the plot
        title (str): plot title
        no_agg_color (List, optional): Color palette for the non-aggregated data. Defaults to BLUE_COLOR_LIST.
        agg_color (List, optional): Color palette for the aggregated data (same length). Defaults to RED_COLOR_LIST.
        agg_diff_color (List, optional): Color palette for the non-aggregated data (different length). Defaults to GREEN_COLOR_LIST.
    """
    plt.figure(figsize=(8, 6))
    ax = plt.subplot(1, 1, 1)

    ax = fitter_plot(agg_fit, "agg same length", ax, agg_color, mode="agg")
    ax = fitter_plot(agg_diff_fit, "agg different length", ax, agg_diff_color, mode="agg diff")

    xdata = no_agg_fit.cliff_lengths[0]
    ydata = no_agg_fit.ydata[0]
    # Plot the mean
    ax.plot(xdata, ydata['mean'], color=no_agg_color[2], linestyle='--', linewidth=2, label=f"no aggregation")

    ax.tick_params(labelsize=16)
    ax.set_xlabel('Clifford Length (Circuit Depth)', fontsize=18)
    ax.set_ylabel('Fidelity', fontsize=18)
    ax.grid(True)
    ax.set_ylim([0.17,1])

    plt.legend(fontsize=16)
    
    plt.title(title, fontsize=18)
    plt.savefig(path, format="pdf", bbox_inches = 'tight')
    log.info(f"Created plot {path}")

    
if __name__ == "__main__":
    log = get_logger("Evaluate")
    path = "rb_data/2021-04-07-18-00-41_merged_3"
    path_time_1 = "rb_data/2021-03-31-07-04-14"
    path_time_2 = "rb_data/2021-04-08-09-09-29"
    path_time_3 = "rb_data/2021-04-08-11-37-57"
    path_diff = "rb_data/2021-04-11-15-07-26"
    # paths = ["rb_data/2021-03-10-10-13-47", "rb_data/2021-03-10-09-15-05", "rb_data/2021-03-09-19-01-22", "rb_data/2021-03-09-17-47-34", \
    #         "rb_data/2021-03-12-08-38-08", "rb_data/2021-03-12-09-32-49", "rb_data/2021-03-12-10-42-06", "rb_data/2021-03-12-11-20-39", \
    #         "rb_data/2021-03-12-12-03-05", "rb_data/2021-03-12-12-55-45", "rb_data/2021-03-12-13-40-43", "rb_data/2021-03-13-15-46-28", \
    #         "rb_data/2021-03-13-16-38-24", "rb_data/2021-03-15-15-00-03", "rb_data/2021-03-15-16-32-00"]
    # paths_2 = ["rb_data/2021-03-31-07-04-14", "rb_data/2021-03-31-09-04-34", "rb_data/2021-03-31-11-01-49", "rb_data/2021-04-08-06-57-10", "rb_data/2021-04-08-09-09-29", "rb_data/2021-04-08-11-37-57"]
    # merge_separate_result_files_all_backends(path, log)
    # merge(paths_2, "./rb_data", log)
    evaluate_dir(path, log)
    all_backends_mean_graph(path, log)
    evaluate_dir(path_time_1, log)
    evaluate_dir(path_time_2, log)
    evaluate_dir(path_time_3, log)
    evaluate_different_length_agg_dir(path_diff, log)
    

    