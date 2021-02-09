import numpy as np
from numpy.core.defchararray import equal

def chi_2(result_distribution:np.ndarray, expected_distribution:np.ndarray) -> float:
    assert(len(result_distribution)==len(expected_distribution))
    not_zero = np.where(expected_distribution != 0)[0]
    return np.sum(np.square(result_distribution[not_zero]-expected_distribution[not_zero])/expected_distribution[not_zero])

def chi_2_diff(result_dist_1:np.ndarray, result_dist_2:np.ndarray, expected_dist:np.ndarray) -> float:
    c2_1 = chi_2(result_dist_1, expected_dist)
    c2_2 = chi_2(result_dist_2, expected_dist)
    return c2_1 - c2_2


if __name__ == "__main__":
    a = np.array([0,0,1,0])
    b = np.array([0,1,0,0]) 

    print(chi_2(a, b))

