import json
import os
import numpy as np
from numpy.core.fromnumeric import clip
from qiskit import circuit
from evaluate.metrics import metric_diff, kullback_leibler_divergence, bhattacharyya_difference, same_order, same_max, chi_square, fidelity
from evaluate.util import round_array, reject_outliers
import qiskit_helper_functions.metrics as metrics
import matplotlib.pyplot as plt
from evaluate.half_violins import draw_violins

from evaluate.colors import RED_COLOR_LIST, BLUE_COLOR_LIST, GREEN_COLOR_LIST

def histogram(values, agg_values, name, filename, range=None):
    plt.figure(figsize=(8, 6))
    ax = plt.subplot(1, 1, 1)
    ax.hist([values, agg_values], range=range, histtype="bar", color=[BLUE_COLOR_LIST[1], RED_COLOR_LIST[1]], label=["no aggregation", "aggregation"])
    ax.tick_params(labelsize=13)
    ax.set_xlabel('Fidelity',  fontsize=20)
    ax.set_ylabel('Count', fontsize=20)
    plt.title(name, fontsize=20)
    plt.legend(fontsize=16)
    plt.savefig(filename, bbox_inches = 'tight')
    plt.close()



def set_axis_style(ax, labels):
    ax.xaxis.set_tick_params(direction='out')
    ax.xaxis.set_ticks_position('bottom')
    ax.set_xticks(np.arange(1, len(labels) + 1))
    ax.set_xticklabels(labels)
    ax.set_xlim(0.25, len(labels) + 0.75)

def violin_plot(values, agg_values, labels, title, filename):
    data = list(zip(values, agg_values, labels))
    data.sort(key=lambda item : item[2])

    values, agg_values, labels = list(zip(*data))

    plt.figure(figsize=(8, 6))
    ax = plt.subplot(1, 1, 1)
    draw_violins(ax, values, None, BLUE_COLOR_LIST, widths=0.95, alpha=1, showmeans=True, mode="right")
    draw_violins(ax, agg_values, None, RED_COLOR_LIST, widths=0.95, alpha=1, showmeans=True, mode="left")
    set_axis_style(ax, labels)
    ax.set_xlabel('Quantum Circuit', fontsize=18)
    ax.set_ylabel('Fidelity', fontsize=18)
    plt.title(title, fontsize=18)
    plt.savefig(filename, bbox_inches = 'tight')
    plt.close()
    

def print_eval(data_list, digits=4):
    print(f"min {round(min(data_list), digits)}")
    print(f"max {round(max(data_list), digits)}")
    print(f"mean {round(np.mean(data_list), digits)}")

def print_latex(data_list, agg_data_list, digits=4):
    print(f"& {round(min(data_list), digits)} & {round(max(data_list), digits)} & {round(np.mean(data_list), digits)} & {round(min(agg_data_list), digits)} & {round(max(agg_data_list), digits)} & {round(np.mean(agg_data_list), digits)} \\\\")

def evaluate_file(file_path):
    # read file
    with open(file_path, 'r') as myfile:
        data=myfile.read()

    file_name = os.path.basename(file_path)
    dir_path =  os.path.dirname(file_path) +"/plots"

    try:
        os.makedirs(dir_path)
        print(f"Created directory {dir_path}")
    except FileExistsError:
        print(f"Directory {dir_path} already exists")

    
    

    # parse file
    obj = json.loads(data)
    n_data = len(obj['data'])
    shots = obj['shots']
    count_better_c2 = 0
    count_better_bc = 0
    agg_count_max_errors = 0
    agg_count_max = 0
    agg_count_order_errors = 0
    agg_count_order = 0
    count_max_errors = 0
    count_max = 0
    count_order_errors = 0
    count_order = 0
    cutqc_agg_c2_list = []
    cutqc_c2_list = []
    agg_c2_list = []
    c2_list = []
    agg_bc_list = []
    bc_list = []
    agg_fid_list = []
    fid_list = []
    for i in range(n_data):
        item = obj["data"][i]
        sv_res_prob = np.array(item["sv-result"])
        sv_res_prob = round_array(sv_res_prob, 1/shots)
        length = len(sv_res_prob)
        agg_res_prob = np.array(item["agg-result"][:length])
        res_prob = np.array(item["result"][:length])
        c2_diff = metric_diff(agg_res_prob, res_prob, sv_res_prob, chi_square)
        cutqc_agg_c2_list.append(metrics.chi2_distance(agg_res_prob, sv_res_prob, True))
        agg_c2_list.append(chi_square(agg_res_prob, sv_res_prob))
        c2_list.append(chi_square(res_prob, sv_res_prob))
        cutqc_c2_list.append(metrics.chi2_distance(res_prob, sv_res_prob, True))
        bc_diff = metric_diff(agg_res_prob, res_prob, sv_res_prob, bhattacharyya_difference)
        bc_list.append(bhattacharyya_difference(res_prob, sv_res_prob))
        agg_bc_list.append(bhattacharyya_difference(agg_res_prob, sv_res_prob))
        fid_list.append(fidelity(res_prob, sv_res_prob))
        agg_fid_list.append(fidelity(agg_res_prob, sv_res_prob))
        if c2_diff < 0:
            count_better_c2 += 1
        if bc_diff < 0:
            count_better_bc += 1
        if same_max(agg_res_prob, sv_res_prob):
            agg_count_max += 1
        if same_order(agg_res_prob, sv_res_prob):
            agg_count_order += 1
        if not same_max(agg_res_prob, sv_res_prob) and same_max(res_prob, sv_res_prob):
            agg_count_max_errors += 1
        if not same_order(agg_res_prob, sv_res_prob) and same_order(res_prob, sv_res_prob):
            agg_count_order_errors += 1
        if same_max(res_prob, sv_res_prob):
            count_max += 1
        if same_order(res_prob, sv_res_prob):
            count_order += 1
        if not same_max(res_prob, sv_res_prob) and same_max(agg_res_prob, sv_res_prob):
            count_max_errors += 1
        if not same_order(res_prob, sv_res_prob) and same_order(agg_res_prob, sv_res_prob):
            count_order_errors += 1
    
    
    # print("#"*20+"Aggregation"+"#"*20)
    # print(f"Chi-squared: Better in {count_better_c2} of {n_data} cases")
    # print(f"Bhattacharyya: Better in {count_better_bc} of {n_data} cases")
    # print(f"Same max value in {agg_count_max} of {n_data} cases")
    # print(f"Relative max errors {agg_count_max_errors}")
    # print(f"Same order in {agg_count_order} of {n_data} cases")
    # print(f"Relative order errors {agg_count_order_errors}")
    # print("#"*20+"No Aggregation"+"#"*20)
    # print(f"Chi-squared: Better in {n_data - count_better_c2} of {n_data} cases")
    # print(f"Bhattacharyya: Better in {n_data - count_better_bc} of {n_data} cases")
    # print(f"Same max value in {count_max} of {n_data} cases")
    # print(f"Relative max errors {count_max_errors}")
    # print(f"Same order in {count_order} of {n_data} cases")
    # print(f"Relative order errors {count_order_errors}")


    backend_name = obj['backend']['name']
    circuit_type = obj['circuit_type']
    histogram(fid_list, agg_fid_list, f"{n_data} {circuit_type} circuits on {backend_name}", f"{dir_path}/{backend_name}_{circuit_type}_hist_fid.pdf")

    print("\n")
    print("#"*5 + f" {backend_name}//{circuit_type} no aggregation:")
    print_eval(fid_list)
    print("#"*5 + f" {backend_name}//{circuit_type} aggregation:")
    print_eval(agg_fid_list)
    print_latex(fid_list, agg_fid_list)
    print("\n")

    return backend_name, circuit_type, fid_list, agg_fid_list




if __name__ == "__main__":
    path = "./agg_data_circ/2021-04-14-14-30-09/ibmq_athens"
    files = []
    for (dirpath, dirnames, filenames) in os.walk(path):
        files.extend(filenames)
        break
    print(f"found the following files {files}")
    fid_lists = []
    agg_fid_lists = []
    labels = []
    for file in files:
        if file == ".DS_Store":
            continue
        print(f"Evaluate file {file}")
        backend_name, circuit_type, fid_list, agg_fid_list = evaluate_file(file_path=path + "/" + file)
        fid_lists.append(fid_list)
        agg_fid_lists.append(agg_fid_list)
        labels.append(circuit_type)
    
    
    violin_plot(fid_lists, agg_fid_lists, labels, f"Fidelity Distributions for {backend_name}", f"{path}/plots/{backend_name}_fidelity_overview.pdf")