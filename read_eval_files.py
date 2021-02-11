import json
import numpy as np
from evaluate.metrics import metric_diff, kullback_leibler_divergence, bhattacharyya_difference, same_order, same_max, chi_square


if __name__ == "__main__":
    file_name = "./agg_data/2021-02-10-22-00-03.json"
    # read file
    with open(file_name, 'r') as myfile:
        data=myfile.read()

    # parse file
    obj = json.loads(data)
    n_data = len(obj['data'])
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
    for i in range(n_data):
        item = obj["data"][i]
        agg_res_prob = np.array(item["agg-result"])
        res_prob = np.array(item["result"])
        sv_res_prob = np.array(item["sv-result"])
        c2_diff = metric_diff(agg_res_prob, res_prob, sv_res_prob, chi_square)
        bc_diff = metric_diff(agg_res_prob, res_prob, sv_res_prob, bhattacharyya_difference)
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
