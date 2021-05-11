import json
import os
import numpy as np
from seaborn.categorical import _ViolinPlotter
from evaluate.metrics import metric_diff, bhattacharyya_difference, same_order, same_max, chi_square, fidelity
from evaluate.util import round_array
import qiskit_helper_functions.metrics as metrics
import matplotlib.pyplot as plt
from evaluate.half_violins import draw_violins
from matplotlib.patches import PathPatch
import seaborn as sns
import pandas as pd
from matplotlib.transforms import Bbox
from evaluate.colors import RED_COLOR_LIST, BLUE_COLOR_LIST, GREEN_COLOR_LIST, RED_COLOR, BLUE_COLOR

def histogram(values, agg_values, name, filename, labels, range=None):
    plt.figure(figsize=(8, 6))
    ax = plt.subplot(1, 1, 1)
    ax.hist([values, agg_values], range=range, histtype="bar", color=[BLUE_COLOR, RED_COLOR], label=labels)
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

def violin_plot_df(df, x_axis_label, title, filename, hue="Execution Type", inner=None, split=True, palette=[RED_COLOR, BLUE_COLOR], order=None, mode="agg", mean=False):

    figure = plt.figure(figsize=(8, 6))
    ax = plt.subplot(1, 1, 1)
    

    if mean:
        ax = sns.violinplot(x=x_axis_label, y="Fidelity", hue=hue, data=df, inner=inner, linewidth=1 ,palette=palette, scale_hue=False, order=order, ax=ax, scale="area", split=split, width=1, dodge=False)


        means = round(df.groupby([x_axis_label])['Fidelity'].mean(), 4)
        means = means.sort_index(ascending=False)
        print(means)

        n_col = len(ax.collections)
        offset = 0
        if n_col == 3:
            offset = 1

        for xtick in range(n_col):
            
            paths = ax.collections[xtick].get_paths()[0]
            if offset == 1:
                # bug fix for bv on ibmq_qasm_simulator
                xtick += offset
                xmin = 0
                xmax = 0
                y_dist_min = np.inf
                y_dist_max = np.inf
                for v in paths.vertices:
                    if v[0] < xtick:
                        if abs(v[1]-means[xtick]) < y_dist_min:
                            y_dist_min=abs(v[1]-means[xtick])
                            xmin = v[0]
                    else:
                        if abs(v[1]-means[xtick]) < y_dist_max:
                            y_dist_max=abs(v[1]-means[xtick])
                            xmax = v[0]
                line = ax.hlines(means[xtick], xmin, xmax, color='black', linewidths=2)
            else:
                line = ax.hlines(means[xtick], xtick-0.5, xtick+0.5, color='black', linewidths=2)
                mask = PathPatch(paths, visible=False)
                ax.add_patch(mask)
                line.set_clip_path(mask)

    else:
        ax = sns.violinplot(x=x_axis_label, y="Fidelity", hue=hue, data=df, inner=inner, linewidth=1 ,palette=palette, scale_hue=True, order=order, ax=ax, scale="area", split=split, width=0.95)
        if mode=="agg":
            plt.legend(loc='upper left')
        elif mode == "part":
            plt.legend(loc='upper center')
    ax.set_xlabel(x_axis_label, fontsize=16)
    ax.set_ylabel('Fidelity', fontsize=16)
    ax.tick_params(labelsize=11)
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
    x_axis_label = "Max Qubit Number of Subcircuits"
    no_cut_label = "No Cut"
    for value in values_flat:
        data.append({x_axis_label:no_cut_label, "Fidelity":value})
    
    index_labels = list(enumerate(labels))
    index_labels.sort(key=lambda x:x[1], reverse=True)
    for i, label in index_labels:
        for mod_value in  mod_values[i]:
            data.append({x_axis_label:str(label), "Fidelity":mod_value})
            
    df = pd.DataFrame.from_dict(data)

    labels.sort(reverse=True)
    order = [no_cut_label]
    for label in labels:
        order.append(str(label))

    for label in order:
        mean = df[df[x_axis_label]==label]["Fidelity"].mean()
        # print(f"{label} mean: {mean}")
    

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
        backend_name, circuit_type, fid_list, mod_fid_list = evaluate_file(file_path=path + "/" + file, mode=mode)
        if diagram == "qpu" and backend_name == "ibmq_qasm_simulator":
            continue
        fid_lists.append(fid_list)
        mod_fid_lists.append(mod_fid_list)
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
        print(backend_name, circuit_type)
        violin_plot_circuits(fid_lists[circuit_type], mod_fid_lists[circuit_type], cut_labels[circuit_type], f"Cuts of {circuit_type} on {backend_name}", f"{path}/plots/{circuit_type}_cuts_fidelity_overview.pdf")

      

def overall_plot(path, mode="part"):
    files = []
    for (dirpath, dirnames, filenames) in os.walk(path):
        for file in filenames:
            if file.endswith(".json"):
                files.append(f"{dirpath}/{file}")
    if mode == "agg":
        with_modification = "aggregation"
        without_modification = "no aggregation"
    else:
        with_modification = "partition"
        without_modification = "no partition"
    data = []
    circuit_types = []
    for file in files:
        backend_name, circuit_type, fid_list, mod_fid_list = evaluate_file(file_path=file, mode=mode)
        if circuit_type not in circuit_types:
            circuit_types.append(circuit_type)
        for value in mod_fid_list:
            data.append({"QPU":backend_name, "Quantum Circuit": circuit_type, "Fidelity":value, "Execution Type":with_modification})
        for value in fid_list:
            data.append({"QPU":backend_name, "Quantum Circuit": circuit_type, "Fidelity":value, "Execution Type":without_modification})

    circuit_types.sort()
    df = pd.DataFrame.from_dict(data)
    df_without_sim = df[df.QPU != "ibmq_qasm_simulator"]

    plot = sns.catplot(x = "QPU",
            y = "Fidelity",
            hue = "Execution Type",
            col = "Quantum Circuit",
            data = df_without_sim,
            kind = "violin",
            split = True,
            palette=[RED_COLOR, BLUE_COLOR],
            inner = None,
            legend_out = False,
            width=0.95,
            aspect=0.7,
            col_order = circuit_types,
            scale_hue=False)
    plot.set_xticklabels(rotation=45)
    plot.tight_layout()
    for a in plot.axes_dict.values():
        a.grid()
    plot.fig.subplots_adjust(top=0.88)
    plot.fig.suptitle('Fidelity Distributions for different Quantum Circuits and QPUS', fontsize=16)
    plt.savefig(f"{path}/all.pdf", bbox_inches = 'tight')
    plt.close()

    mean_df = df_without_sim.groupby(['Quantum Circuit','Execution Type'], as_index=False)['Fidelity'].mean()

    bar_plot = sns.barplot(x = "Quantum Circuit",
            y = "Fidelity",
            hue = "Execution Type",
            data = mean_df,
            palette=[RED_COLOR, BLUE_COLOR],
            hue_order=[with_modification, without_modification])
    for p in bar_plot.patches:
        bar_plot.annotate(format(p.get_height(), '.3f'), 
                    (p.get_x() + p.get_width() / 2., p.get_height()), 
                    ha = 'center', va = 'center', 
                    xytext = (0, 5), 
                    textcoords = 'offset points',
                    fontsize= 14)
    bar_plot.set_ylim(0, 1.05)
    plt.tick_params(labelsize=14)
    plt.xlabel("Quantum Circuit", size=16)
    plt.ylabel("Average Fidelity", size=16)
    plt.legend(fontsize=16, loc='upper center', bbox_to_anchor=(0.5, -0.15))
    plt.savefig(f"{path}/circuit_avg_fidelity.pdf", bbox_inches = 'tight')
    plt.close()
    
    non_partitioned_df = pd.DataFrame(df[df["Execution Type"] == without_modification])
    
    print(non_partitioned_df)

    non_partitioned_df['QPU'] = np.where(non_partitioned_df['QPU'] == "ibmq_qasm_simulator", "ibmq_qasm_simulator", "averaged QPUs")
    print(non_partitioned_df)
    
    qpu_vs_sim_df = non_partitioned_df.groupby(['Quantum Circuit', 'QPU']).mean()
    qpu_vs_sim_df.reset_index(inplace=True)

    print(qpu_vs_sim_df)

    bar_plot = sns.barplot(x = "Quantum Circuit",
            y = "Fidelity",
            hue = "QPU",
            data = qpu_vs_sim_df,
            palette = "viridis")

    for p in bar_plot.patches:
        bar_plot.annotate(format(p.get_height(), '.3f'), 
                    (p.get_x() + p.get_width() / 2., p.get_height()), 
                    ha = 'center', va = 'center', 
                    xytext = (0, 5), 
                    textcoords = 'offset points',
                    fontsize= 14)
    bar_plot.set_ylim(0, 1.05)
    plt.tick_params(labelsize=14)
    plt.xlabel("Quantum Circuit", size=16)
    plt.ylabel("Average Fidelity", size=16)
    plt.legend(fontsize=16, loc='upper center', bbox_to_anchor=(0.5, -0.15))
    plt.savefig(f"{path}/qpu_sim_avg_fidelity.pdf", bbox_inches = 'tight')
    plt.close()




if __name__ == "__main__":
    # overall_plot("./part_data/2021-04-18-07-11-18-test")
    # eval_dir_cuts("part_data/2021-04-20-06-05-22")
    #eval_dir("./part_data/2021-04-18-07-11-18/qpu_adder", "part", "qpu")
    # eval_dir("./part_data/2021-04-18-07-11-18/qpu_bv", "part", "qpu")
    # eval_dir("./part_data/2021-04-18-07-11-18/qpu_supremacy_linear", "part", "qpu")

    eval_dir("part_data/2021-04-18-07-11-18/ibmq_qasm_simulator", "part", "circuits")
    eval_dir("part_data/2021-04-18-07-11-18/ibmq_athens", "part", "circuits")
    eval_dir("part_data/2021-04-18-07-11-18/ibmq_belem", "part", "circuits")
    eval_dir("part_data/2021-04-18-07-11-18/ibmq_lima", "part", "circuits")
    eval_dir("part_data/2021-04-18-07-11-18/ibmq_quito", "part", "circuits")
    eval_dir("part_data/2021-04-18-07-11-18/ibmq_santiago", "part", "circuits")

    # eval_dir("./agg_data_circ/2021-04-14-14-30-09/ibmq_athens")
    # eval_dir("./agg_data_circ/2021-04-14-14-35-23/ibmq_belem")
    # eval_dir("./agg_data_circ/2021-04-14-15-16-27/ibmq_santiago")
    # eval_dir("./agg_data_circ/2021-04-14-15-32-54/ibmq_quito")
    # eval_dir("./agg_data_circ/2021-04-14-15-50-01/ibmq_lima")
    