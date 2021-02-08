import numpy as np
from numpy.core.defchararray import equal

def chi_2(result_distribution:np.ndarray, expected_distribution:np.ndarray) -> float:
    assert(len(result_distribution)==len(expected_distribution))
    return np.sum(np.nan_to_num(np.square(result_distribution-expected_distribution)/expected_distribution))

def chi_2_diff(result_dist_1:np.ndarray, result_dist_2:np.ndarray, expected_dist:np.ndarray) -> float:
    c2_1 = chi_2(result_dist_1, expected_dist)
    c2_2 = chi_2(result_dist_2, expected_dist)
    return c2_1 - c2_2