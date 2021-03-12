from datetime import datetime
import os
from randomized_benchmarking import store_general_data
from matplotlib.axes import Axes
import copy

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

def fitter_plot(rb_fit:RBFitter, name:str, ax:Optional[Axes]=None, color:List = None):
    if not ax:
        plt.figure(figsize=(8, 6))
        ax = plt.subplot(1, 1, 1)
    prev_lines = copy.copy(ax.lines)
    # Plot the essence by calling plot_rb_data
    rb_fit.plot_rb_data(0, ax=ax, add_label=False, show_plt=False)
    data_label_flag = True
    for line in ax.lines:
        if not line in prev_lines:
            if color:
                c = line.get_color()
                if c == "gray":
                    line.set_color(color[0])
                    if data_label_flag:
                        line.set_label(f"{name} data")
                        data_label_flag = False
                elif c == "r":
                    line.set_color(color[1])
                    line.set_label(f"{name} mean")
                elif c == "blue":
                    line.set_color(color[2])
                    line.set_label(f"{name} fitted func")
        
    # Add title and label
    # ax.set_title('%d Qubit RB - %s'%(nQ, name), fontsize=18)

    # plt.savefig(filename)
    # log.info("Saved file " + filename)
    return ax

def fit(results:List[Result], rb_opts:Dict, xdata:List, log:Logger) -> RBFitter:
    rb_fit = RBFitter(None, xdata, rb_opts['rb_pattern'])
    rb_fit.add_data(results)
    log.info(f"Fitted {len(results)} results, alpha: {rb_fit.fit[0]['params'][1]}, EPC: {rb_fit.fit[0]['epc']}")
    # batch_size = len(rb_opts['length_vector'])
    # for rb_seed in range(rb_opts['nseeds']):
    #     result_batch = results[rb_seed*batch_size: rb_seed*batch_size + batch_size]
    #     rb_fit.add_data(result_batch)
    #     log.info('After seed %d, alpha: %f, EPC: %f'%(rb_seed,rb_fit.fit[0]['params'][1], rb_fit.fit[0]['epc']))
    return rb_fit

def evaluate(results:List[Result], rb_opts:Dict, xdata:List, dir_path, backend_name:str, log:Logger):
    half = len(results)//2
    no_agg_results = results[:half] 
    agg_results = results[half:]
    assert(len(no_agg_results)==len(agg_results))

    log.info(f"Fit no agg data for backend {backend_name}")
    no_agg_fit = fit(no_agg_results, rb_opts, xdata, log)
    ax = fitter_plot(no_agg_fit, "no agg", color=ORANGE_COLOR_LIST)
    log.info(f"Fit agg data for backend {backend_name}")
    agg_fit = fit(agg_results, rb_opts, xdata, log)
    ax = fitter_plot(agg_fit, "agg", ax=ax, color=LIGHT_BLUE_COLOR_LIST)
    plt.title(f"RB for {backend_name}")
    plt.legend()
    plt.savefig(f"{dir_path}/{backend_name}/{backend_name}_together.png")

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
    result_path = f"{result_path}/{now_str}_merged/_{len(dir_paths)}"
    os.mkdir(result_path)

    rb_opts_merged['nseeds'] = nseeds_merged

    store_general_data(results_merged, rb_opts_merged, xdata_merged, result_path, log)

    for backend_name, results in results_merged.items():
        backend_data_path = f"{result_path}/{backend_name}/data"
        os.makedirs(backend_data_path)
        backend_results = []
        backend_results.extend(results["no_agg"])
        backend_results.extend(results["agg"])
        pickle_dump(backend_results, f"{backend_data_path}/results.pkl")
        pickle_dump(backends[backend_name], f"{backend_data_path}/backend_dict.pkl")
        log.info(f"Pickeld all files for backend {backend_name}")

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
    path = "rb_data/2021-03-12-10-41-20_merged"
    paths = ["rb_data/2021-03-10-10-13-47", "rb_data/2021-03-10-09-15-05", "rb_data/2021-03-09-19-01-22", "rb_data/2021-03-09-17-47-34", "rb_data/2021-03-12-08-38-08"]
    # merge(paths, "./rb_data", log)
    evaluate_dir(path, log)
    # merge_separate_result_files_all_backends(path, log)
    