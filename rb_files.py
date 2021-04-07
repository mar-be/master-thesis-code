from datetime import datetime
import os
from randomized_benchmarking import store_general_data
from matplotlib.axes import Axes
import itertools

from qiskit.providers import backend
from logger import get_logger
from logging import Logger
from typing import Any, Dict, List, Optional
import pickle
from qiskit.ignis.verification.randomized_benchmarking.fitters import RBFitter
import matplotlib.pyplot as plt

import numpy as np

from qiskit.result.result import Result

BLUE_COLOR_LIST = ["#8080ff", "#0000ff", "#000080" ]
RED_COLOR_LIST = ["#ff8080", "#ff0000", "#800000" ]
LIGHT_BLUE_COLOR_LIST = ["#80ccff", "#0099ff", "#004c80" ]
GREEN_COLOR_LIST = ["#80ff80", "#00ff00", "#008000" ]
LIGHT_GREEN_COLOR_LIST = ["#80ffcc", "#00ff99", "#00804d" ]
ORANGE_COLOR_LIST = ["#ffcc80", "#ff9900", "#804d00" ]

def pickle_load(filename:str) -> Any:
    with open(filename,'rb') as f:
        return pickle.load(f)

def pickle_dump(object, filename):
    with open(filename,'wb') as f:
        pickle.dump(object, f)

def plot(no_agg_fit:RBFitter, agg_fit:RBFitter, path:str, title:str, log:Logger, no_agg_color:List = BLUE_COLOR_LIST, agg_color: List = RED_COLOR_LIST):
    plt.figure(figsize=(8, 6))
    ax = plt.subplot(1, 1, 1)

    ax = fitter_plot(agg_fit, "agg", ax, agg_color, x_shift=-1, mode="agg")
    ax = fitter_plot(no_agg_fit, "no agg", ax, no_agg_color, x_shift=1, mode="no agg")

    ax.tick_params(labelsize=16)
    ax.set_xlabel('Clifford Length', fontsize=18)
    ax.set_ylabel('Ground State Population', fontsize=20)
    ax.grid(True)

    handles, labels = ax.get_legend_handles_labels()
    order = [0,1,2,3,4,5]
    #plt.legend([handles[idx] for idx in order],[labels[idx] for idx in order], fontsize=16)
    plt.legend()
    
    plt.title(title, fontsize=18)
    plt.savefig(path, format="pdf")
    log.info(f"Created plot {path}")
        
def draw_violins(ax, data, positions, color, widths=12, alpha = 0.5, showmeans=False, mode="agg"):
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

def fitter_plot(rb_fit:RBFitter, name:str, ax:Optional[Axes], color:List, pattern_index=0, x_shift=0, mode="agg"):
    
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
    ax.plot(xdata, ydata['mean'], color=color[2], linestyle='-', linewidth=2, label=f"{name} mean")

    return ax

def fit_data(results:List[Result], rb_opts:Dict, xdata:List, log:Logger) -> RBFitter:
    rb_fit = RBFitter(None, xdata, rb_opts['rb_pattern'])
    rb_fit.add_data(results)
    rb_fit._nseeds = range(rb_opts["nseeds"])
    log.info(f"Fitted {len(results)} results, alpha: {rb_fit.fit[0]['params'][1]}, EPC: {rb_fit.fit[0]['epc']}")
    return rb_fit

def evaluate(results:List[Result], rb_opts:Dict, xdata:List, dir_path, backend_name:str, log:Logger):
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
    plot(no_agg_fit, agg_fit, f"{dir_path}/{backend_name}/{backend_name}_together.pdf", f"{n_qubits} Qubit RB for {backend_name} with {int(len(agg_results)/n_sizes)} circuit per length", log)
    

def get_general_data(path:str):
    rb_circs = pickle_load(f"{path}/general_data/rb_circs.pkl")
    rb_opts = pickle_load(f"{path}/general_data/rb_opts.pkl")
    xdata = pickle_load(f"{path}/general_data/xdata.pkl")
    return rb_circs, rb_opts, xdata

def get_backend_data(path:str, backend_name:str):
    backend_dict = pickle_load(f"{path}/{backend_name}/data/backend_dict.pkl")
    results = pickle_load(f"{path}/{backend_name}/data/results.pkl")
    return backend_dict, results
    
def evaluate_dir(path:str, log:Logger):
    backend_names = get_backends_in_dir(path)
    for backend_name in backend_names:
        log.info(f"Evaluate backend {backend_name}")
        evaluate_files(path, backend_name, log)

def evaluate_files(path:str, backend_name:str, log:Logger):
    rb_circs, rb_opts, xdata = get_general_data(path)
    backend_dict, results = get_backend_data(path, backend_name)
    evaluate(results, rb_opts, xdata, path, backend_name, log)

def get_backends_in_dir(path:str):
    backend_names = []
    for (dirpath, dirnames, filenames) in os.walk(path):
        backend_names.extend(dirnames)
        break
    backend_names.remove("general_data")
    return backend_names

def check_or_init(var:Any, other_var:Any):
    if not var is None:
        if isinstance(var, np.ndarray):
            if np.any(var != other_var):
                raise ValueError(f"{var} and {other_var} are not compatible")
        elif var != other_var:
            raise ValueError(f"{var} and {other_var} are not compatible")
    return other_var
    

def merge(dir_paths: List[str], result_path: str, log:Logger):
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

def merge_separate_result_files(path:str, backend_name:str):
    agg_path = f"{path}/{backend_name}/data/res_agg"
    no_agg_path = f"{path}/{backend_name}/data/res_no_agg"
    no_agg_files = []
    for (dirpath, dirnames, filenames) in os.walk(no_agg_path):
        no_agg_files.extend(filenames)
    agg_files = []
    for (dirpath, dirnames, filenames) in os.walk(agg_path):
        agg_files.extend(filenames)

    reverse_string_func = lambda s: s[::-1]
    no_agg_files.sort(key=reverse_string_func)
    agg_files.sort(key=reverse_string_func)

    results = []

    for file in no_agg_files:
        res = pickle_load(f"{no_agg_path}/{file}")
        results.append(res)

    for file in agg_files:
        res = pickle_load(f"{agg_path}/{file}")
        results.append(res)

    pickle_dump(results, f"{path}/{backend_name}/data/results.pkl")

    
def merge_separate_result_files_all_backends(path:str, log:Logger):
    backends = get_backends_in_dir(path)
    for backend_name in backends:
        log.info(f"Merge results for backend {backend_name}")
        merge_separate_result_files(path, backend_name)


if __name__ == "__main__":
    log = get_logger("Evaluate")
    path = "rb_data/2021-04-07-18-00-41_merged_3"
    paths = ["rb_data/2021-03-10-10-13-47", "rb_data/2021-03-10-09-15-05", "rb_data/2021-03-09-19-01-22", "rb_data/2021-03-09-17-47-34", \
            "rb_data/2021-03-12-08-38-08", "rb_data/2021-03-12-09-32-49", "rb_data/2021-03-12-10-42-06", "rb_data/2021-03-12-11-20-39", \
            "rb_data/2021-03-12-12-03-05", "rb_data/2021-03-12-12-55-45", "rb_data/2021-03-12-13-40-43", "rb_data/2021-03-13-15-46-28", \
            "rb_data/2021-03-13-16-38-24", "rb_data/2021-03-15-15-00-03", "rb_data/2021-03-15-16-32-00"]
    paths_2 = ["rb_data/2021-03-31-07-04-14", "rb_data/2021-03-31-09-04-34", "rb_data/2021-03-31-11-01-49"]
    # merge_separate_result_files_all_backends(path, log)
    evaluate_dir(path, log)
    # merge(paths_2, "./rb_data", log)
    

    