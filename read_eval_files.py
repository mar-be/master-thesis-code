import json
import numpy as np
from evaluate.metrics import metric_diff, kullback_leibler_divergence, bhattacharyya_difference, same_order, same_max, chi_square
from evaluate.util import round, reject_outliers
import matplotlib.pyplot as plt

def line_plot(values, agg_values, name):
    plt.plot(values, label="no aggregation")
    plt.plot(agg_values, label="aggregation")
    plt.title(name)
    plt.legend()
    plt.show()


def histogram(values, agg_values, name, range=None):
    plt.hist([values, agg_values], range=range, histtype="bar", log=True, label=["no aggregation", "aggregation"])
    plt.title(name)
    plt.legend()
    plt.show()

if __name__ == "__main__":
    file_name = "./agg_data/growing_depth_2021-02-23-13-02-54/ibmq_athens.json"
    # read file
    with open(file_name, 'r') as myfile:
        data=myfile.read()

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
    agg_c2_list = []
    c2_list = []
    agg_bc_list = []
    bc_list = []
    for i in range(n_data):
        item = obj["data"][i]
        agg_res_prob = np.array(item["agg-result"])
        res_prob = np.array(item["result"])
        sv_res_prob = np.array(item["sv-result"])
        sv_res_prob = round(sv_res_prob, 1/shots)
        c2_diff = metric_diff(agg_res_prob, res_prob, sv_res_prob, chi_square)
        agg_c2_list.append(chi_square(agg_res_prob, sv_res_prob))
        c2_list.append(chi_square(res_prob, sv_res_prob))
        bc_diff = metric_diff(agg_res_prob, res_prob, sv_res_prob, bhattacharyya_difference)
        bc_list.append(bhattacharyya_difference(res_prob, sv_res_prob))
        agg_bc_list.append(bhattacharyya_difference(agg_res_prob, sv_res_prob))
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
    
    
    print("#"*20+"Aggregation"+"#"*20)
    print(f"Chi-squared: Better in {count_better_c2} of {n_data} cases")
    print(f"Bhattacharyya: Better in {count_better_bc} of {n_data} cases")
    print(f"Same max value in {agg_count_max} of {n_data} cases")
    print(f"Relative max errors {agg_count_max_errors}")
    print(f"Same order in {agg_count_order} of {n_data} cases")
    print(f"Relative order errors {agg_count_order_errors}")
    print("#"*20+"No Aggregation"+"#"*20)
    print(f"Chi-squared: Better in {n_data - count_better_c2} of {n_data} cases")
    print(f"Bhattacharyya: Better in {n_data - count_better_bc} of {n_data} cases")
    print(f"Same max value in {count_max} of {n_data} cases")
    print(f"Relative max errors {count_max_errors}")
    print(f"Same order in {count_order} of {n_data} cases")
    print(f"Relative order errors {count_order_errors}")



    line_plot(c2_list, agg_c2_list, "Chi Squared")
    line_plot(bc_list, agg_bc_list, "Bhattacharyya Difference")


    histogram(c2_list, agg_c2_list, "Chi Squared")
    histogram(c2_list, agg_c2_list, "Chi Squared", (0.0, 1.0))
    histogram(bc_list, agg_bc_list, "Bhattacharyya Difference")
    histogram(bc_list, agg_bc_list, "Bhattacharyya Difference", (0.0, 0.1))
