from typing import Callable
import numpy as np
from scipy.stats import entropy

def chi_2(result_distribution:np.ndarray, expected_distribution:np.ndarray) -> float:
    assert(len(result_distribution)==len(expected_distribution))
    not_zero = np.where(expected_distribution != 0)[0]
    return np.sum(np.square(result_distribution[not_zero]-expected_distribution[not_zero])/expected_distribution[not_zero])

def kullback_leibler_divergence(result_distribution:np.ndarray, expected_distribution:np.ndarray) -> float:
    assert(len(result_distribution)==len(expected_distribution))
    return entropy(result_distribution, expected_distribution)

def metric_diff(result_dist_1:np.ndarray, result_dist_2:np.ndarray, expected_dist:np.ndarray, metric:Callable[[np.ndarray, np.ndarray], float]) -> float:
    m_1 = metric(result_dist_1, expected_dist)
    m_2 = metric(result_dist_2, expected_dist)
    return m_1 - m_2

if __name__ == "__main__":
    a = np.array([0,0,1,0])
    b = np.array([0,1,0,0]) 
    c = np.array([1,1,1,1])/4 

    print(chi_2(a, b))
    print(kullback_leibler_divergence(a, b))
    print(kullback_leibler_divergence(a, c))

