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
    ax.xaxis.get_major_formatter().set_useOffset(False)
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

def violin_plot_df(df, x_axis_label, title, filename, hue="Execution Type", split=True, palette=[RED_COLOR_LIST[1], BLUE_COLOR_LIST[1]], order=None, mode="agg"):

    plt.figure(figsize=(8, 6))
    ax = plt.subplot(1, 1, 1)
    sns.violinplot(x=x_axis_label, y="Fidelity", hue=hue, data=df, inner=None, linewidth=1 ,palette=palette, scale_hue=True, order=order, ax=ax, scale="area", split=True)
    if mode=="agg":
        plt.legend(loc='upper left')
    elif mode == "part":
        plt.legend(loc='upper center')
    ax.set_xlabel(x_axis_label, fontsize=14)
    ax.set_ylabel('Fidelity', fontsize=14)
    ax.set_axisbelow(True)
    plt.title(title, fontsize=18)
    plt.grid()
    plt.savefig(filename, bbox_inches = 'tight')
    plt.close()

    
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
    elif diagram == "qpu":
        x_axis_label = "QPU"
    else:
        x_axis_label = "Subcircuit Max Qubits"


    data = []

    for i, label in enumerate(labels):
        for value, mod_value in zip(values[i], mod_values[i]):
            data.append({x_axis_label:label, "Fidelity":mod_value, "Execution Type":with_modification})
            data.append({x_axis_label:label, "Fidelity":value, "Execution Type":without_modification})


    df = pd.DataFrame.from_dict(data)
    print(df)

    violin_plot_df(df, x_axis_label, title, filename, mode=mode)

def violin_plot_circuits(values, mod_values, labels, title, filename):
    values_flat = []
    for value_list in values:
        values_flat.extend(value_list)
    
    data = []
    x_axis_label = "Max Number of Qubits in Subcircuits"
    no_cut_label = "No Cut"
    for value in values_flat:
        data.append({x_axis_label:no_cut_label, "Fidelity":value})
    
    for i, label in enumerate(labels):
        for mod_value in  mod_values[i]:
            data.append({x_axis_label:str(label), "Fidelity":mod_value})
            
    df = pd.DataFrame.from_dict(data)
    df.sort_values(x_axis_label)
    print(df)

    labels.sort(reverse=True)
    order = [no_cut_label]
    for label in labels:
        order.append(str(label))
    
    violin_plot_df(df, x_axis_label, title, filename, hue=None, split=False, palette=None, order=order, mode=None)


def print_eval(data_list, digits=4):
    print(f"min {round(min(data_list), digits)}")
    print(f"max {round(max(data_list), digits)}")
    print(f"mean {round(np.mean(data_list), digits)}")

def print_latex(data_list, agg_data_list, digits=4):
    print(f"& {round(min(data_list), digits)} & {round(max(data_list), digits)} & {round(np.mean(data_list), digits)} & {round(min(agg_data_list), digits)} & {round(max(agg_data_list), digits)} & {round(np.mean(agg_data_list), digits)} \\\\")

def get_fidelity_from_json(json_obj, mode="agg"):
    fid_list = []
    mod_fid_list = []
    n_data = len(json_obj['data'])
    shots = json_obj['shots']
    for i in range(n_data):
        item = json_obj["data"][i]
        sv_res_prob = np.array(item["sv-result"])
        sv_res_prob = round_array(sv_res_prob, 1/shots)
        length = len(sv_res_prob)
        agg_res_prob = np.array(item[f"{mode}-result"][:length]).clip(min=0)
        res_prob = np.array(item["result"][:length]).clip(min=0)
        fid_list.append(fidelity(res_prob, sv_res_prob))
        mod_fid_list.append(fidelity(agg_res_prob, sv_res_prob))
    return fid_list, mod_fid_list

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
    fid_list, mod_fid_list = get_fidelity_from_json(obj, mode)
    
        
    

    backend_name = obj['backend']['name']
    circuit_type = obj['circuit_type']
    histogram(fid_list, mod_fid_list, f"{n_data} {circuit_type} circuits on {backend_name}", f"{dir_path}/{backend_name}_{circuit_type}_hist_fid.pdf", [without_modification, with_modification])

    print("\n")
    print("#"*5 + f" {backend_name}//{circuit_type} {without_modification}:")
    print_eval(fid_list)
    print("#"*5 + f" {backend_name}//{circuit_type} {with_modification}:")
    print_eval(mod_fid_list)
    print_latex(fid_list, mod_fid_list)
    print("\n")

    return backend_name, circuit_type, fid_list, mod_fid_list


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
        if diagram == "qpu" and backend_name == "ibmq_qasm_simulator":
            continue
        fid_lists.append(fid_list)
        mod_fid_lists.append(agg_fid_list)
        type_labels.append(circuit_type)
        qpu_labels.append(backend_name)
    
    if diagram == "circuits":
        violin_plot(fid_lists, mod_fid_lists, type_labels, f"Fidelity Distributions for {backend_name}", f"{path}/plots/{backend_name}_fidelity_overview.pdf", mode, diagram)
    else:
        violin_plot(fid_lists, mod_fid_lists, qpu_labels, f"Fidelity Distributions for {circuit_type}", f"{path}/plots/{circuit_type}_qpu_fidelity_overview.pdf", mode, diagram)


def eval_dir_cuts(path):
    folders = []
    for (dirpath, dirnames, filenames) in os.walk(path):
        folders.extend(dirnames)
        break
    for dir in folders:
        eval_cuts(f"{path}/{dir}")

def eval_cuts(path):
    files = []
    for (dirpath, dirnames, filenames) in os.walk(path):
        files.extend(filenames)
        break
    fid_lists = {}
    mod_fid_lists = {}
    cut_labels = {}
    circuit_types = []
    backend_name = None
    for file in files:
        if file == ".DS_Store":
            continue
        print(f"Evaluate file {file}")
        with open(f"{path}/{file}", 'r') as myfile:
            data=myfile.read()

        # parse file
        obj = json.loads(data)
        backend_name = obj['backend']['name']
        circuit_type = obj['circuit_type']
        sub_qubits = obj['subcircuit_max_qubits']
        fid_list, mod_fid_list = get_fidelity_from_json(obj, "part")

        if not circuit_type in circuit_types:
            circuit_types.append(circuit_type)
            fid_lists[circuit_type] = [fid_list]
            mod_fid_lists[circuit_type] = [mod_fid_list]
            cut_labels[circuit_type] = [sub_qubits]
        else:
            fid_lists[circuit_type].append(fid_list)
            mod_fid_lists[circuit_type].append(mod_fid_list)
            cut_labels[circuit_type].append(sub_qubits)
    try:
        os.makedirs(f"{path}/plots/")
    except FileExistsError:
        pass

    for circuit_type in circuit_types:
        violin_plot_circuits(fid_lists[circuit_type], mod_fid_lists[circuit_type], cut_labels[circuit_type], f"Fidelity Distributions for {circuit_type} on {backend_name}", f"{path}/plots/{circuit_type}_cuts_fidelity_overview.pdf")
        

if __name__ == "__main__":
    eval_dir_cuts("part_data/2021-04-19-15-23-04")
    # eval_dir("./part_data/2021-04-18-07-11-18/qpu_adder", "part", "qpu")
    # eval_dir("./part_data/2021-04-18-07-11-18/qpu_bv", "part", "qpu")
    # eval_dir("./part_data/2021-04-18-07-11-18/qpu_supremacy_linear", "part", "qpu")

    eval_dir("part_data/2021-04-18-07-11-18/ibmq_qasm_simulator", "part", "circuits")
    # eval_dir("part_data/2021-04-18-07-11-18/ibmq_athens", "part", "circuits")
    # eval_dir("part_data/2021-04-18-07-11-18/ibmq_belem", "part", "circuits")
    # eval_dir("part_data/2021-04-18-07-11-18/ibmq_lima", "part", "circuits")
    # eval_dir("part_data/2021-04-18-07-11-18/ibmq_quito", "part", "circuits")
    # eval_dir("part_data/2021-04-18-07-11-18/ibmq_santiago", "part", "circuits")

    # eval_dir("./agg_data_circ/2021-04-14-14-30-09/ibmq_athens")
    # eval_dir("./agg_data_circ/2021-04-14-14-35-23/ibmq_belem")
    # eval_dir("./agg_data_circ/2021-04-14-15-16-27/ibmq_santiago")
    # eval_dir("./agg_data_circ/2021-04-14-15-32-54/ibmq_quito")
    # eval_dir("./agg_data_circ/2021-04-14-15-50-01/ibmq_lima")
    