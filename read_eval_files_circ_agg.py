import json
import os
import numpy as np
from evaluate.metrics import metric_diff, bhattacharyya_difference, same_order, same_max, chi_square, fidelity
from evaluate.util import round_array
import qiskit_helper_functions.metrics as metrics
import matplotlib.pyplot as plt
from evaluate.half_violins import draw_violins
import matplotlib.patches as mpatches
import seaborn as sns
import pandas as pd

from evaluate.colors import RED_COLOR_LIST, BLUE_COLOR_LIST, GREEN_COLOR_LIST

def histogram(values, agg_values, name, filename, labels, range=None):
    plt.figure(figsize=(8, 6))
    ax = plt.subplot(1, 1, 1)
    ax.hist([values, agg_values], range=range, histtype="bar", color=[BLUE_COLOR_LIST[1], RED_COLOR_LIST[1]], label=labels)
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

    
def violin_plot(values, mod_values, labels, title, filename, mode="agg", diagram="circuits"):
    data = list(zip(values, mod_values, labels))
    data.sort(key=lambda item : item[2])

    values, mod_values, labels = list(zip(*data))

    if mode == "agg":
        with_modification = "aggregation"
        without_modification = "no aggregation"
    else:
        with_modification = "partition"
        without_modification = "no partition"

    if diagram == "circuits":
        x_axis_label = "Quantum Circuit"
    else:
        x_axis_label = "QPU"

    data = []

    for i, label in enumerate(labels):
        for value, mod_value in zip(values[i], mod_values[i]):
            data.append({x_axis_label:label, "Fidelity":mod_value, "Execution Type":with_modification})
            data.append({x_axis_label:label, "Fidelity":value, "Execution Type":without_modification})


    df = pd.DataFrame.from_dict(data)
    print(df)

    plt.figure(figsize=(8, 6))
    ax = plt.subplot(1, 1, 1)
    sns.violinplot(x=x_axis_label, y="Fidelity", hue="Execution Type", data=df, inner=None, linewidth=1 ,palette=[RED_COLOR_LIST[1], BLUE_COLOR_LIST[1]],scale_hue=True, ax=ax, scale="area", split=True)
    if mode=="agg":
        plt.legend(loc='upper left')
    else:
        plt.legend(loc='upper center')
    ax.set_xlabel(x_axis_label, fontsize=14)
    ax.set_ylabel('Fidelity', fontsize=14)
    ax.set_axisbelow(True)
    plt.title(title, fontsize=18)
    plt.grid()
    plt.savefig(filename, bbox_inches = 'tight')
    plt.close()

def print_eval(data_list, digits=4):
    print(f"min {round(min(data_list), digits)}")
    print(f"max {round(max(data_list), digits)}")
    print(f"mean {round(np.mean(data_list), digits)}")

def print_latex(data_list, agg_data_list, digits=4):
    print(f"& {round(min(data_list), digits)} & {round(max(data_list), digits)} & {round(np.mean(data_list), digits)} & {round(min(agg_data_list), digits)} & {round(max(agg_data_list), digits)} & {round(np.mean(agg_data_list), digits)} \\\\")

def evaluate_file(file_path, mode="agg"):
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

    if mode == "agg":
        with_modification = "aggregation"
        without_modification = "no aggregation"
    else:
        with_modification = "partition"
        without_modification = "no partition"
    

    # parse file
    obj = json.loads(data)
    n_data = len(obj['data'])
    shots = obj['shots']
    agg_fid_list = []
    fid_list = []
    for i in range(n_data):
        item = obj["data"][i]
        sv_res_prob = np.array(item["sv-result"])
        sv_res_prob = round_array(sv_res_prob, 1/shots)
        length = len(sv_res_prob)
        agg_res_prob = np.array(item[f"{mode}-result"][:length])
        res_prob = np.array(item["result"][:length])
        fid_list.append(fidelity(res_prob, sv_res_prob))
        agg_fid_list.append(fidelity(agg_res_prob, sv_res_prob))
        
    

    backend_name = obj['backend']['name']
    circuit_type = obj['circuit_type']
    histogram(fid_list, agg_fid_list, f"{n_data} {circuit_type} circuits on {backend_name}", f"{dir_path}/{backend_name}_{circuit_type}_hist_fid.pdf", [without_modification, with_modification])

    print("\n")
    print("#"*5 + f" {backend_name}//{circuit_type} {without_modification}:")
    print_eval(fid_list)
    print("#"*5 + f" {backend_name}//{circuit_type} {with_modification}:")
    print_eval(agg_fid_list)
    print_latex(fid_list, agg_fid_list)
    print("\n")

    return backend_name, circuit_type, fid_list, agg_fid_list


def eval_dir(path, mode="agg", diagram="circuits"):
    files = []
    for (dirpath, dirnames, filenames) in os.walk(path):
        files.extend(filenames)
        break
    print(f"found the following files {files}")
    fid_lists = []
    mod_fid_lists = []
    type_labels = []
    qpu_labels = []
    for file in files:
        if file == ".DS_Store":
            continue
        print(f"Evaluate file {file}")
        backend_name, circuit_type, fid_list, agg_fid_list = evaluate_file(file_path=path + "/" + file, mode=mode)
        if backend_name == "ibmq_qasm_simulator":
            continue
        fid_lists.append(fid_list)
        mod_fid_lists.append(agg_fid_list)
        type_labels.append(circuit_type)
        qpu_labels.append(backend_name)
    
    if diagram == "circuits":
        violin_plot(fid_lists, mod_fid_lists, type_labels, f"Fidelity Distributions for {backend_name}", f"{path}/plots/{backend_name}_fidelity_overview.pdf", mode, diagram)
    else:
        violin_plot(fid_lists, mod_fid_lists, qpu_labels, f"Fidelity Distributions for {circuit_type}", f"{path}/plots/{circuit_type}_qpu_fidelity_overview.pdf", mode, diagram)


if __name__ == "__main__":
    eval_dir("./part_data/2021-04-18-07-11-18/qpu_adder", "part", "qpu")
    eval_dir("./part_data/2021-04-18-07-11-18/qpu_bv", "part", "qpu")
    eval_dir("./part_data/2021-04-18-07-11-18/qpu_supremacy_linear", "part", "qpu")

    eval_dir("part_data/2021-04-18-07-11-18/ibmq_athens", "part", "circuits")
    eval_dir("part_data/2021-04-18-07-11-18/ibmq_belem", "part", "circuits")
    eval_dir("part_data/2021-04-18-07-11-18/ibmq_lima", "part", "circuits")
    eval_dir("part_data/2021-04-18-07-11-18/ibmq_quito", "part", "circuits")
    eval_dir("part_data/2021-04-18-07-11-18/ibmq_santiago", "part", "circuits")

    eval_dir("./agg_data_circ/2021-04-14-14-30-09/ibmq_athens")
    eval_dir("./agg_data_circ/2021-04-14-14-35-23/ibmq_belem")
    eval_dir("./agg_data_circ/2021-04-14-15-16-27/ibmq_santiago")
    eval_dir("./agg_data_circ/2021-04-14-15-32-54/ibmq_quito")
    eval_dir("./agg_data_circ/2021-04-14-15-50-01/ibmq_lima")
    