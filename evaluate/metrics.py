from typing import Callable
import numpy as np
from scipy import stats

def chi_square(result_distribution:np.ndarray, expected_distribution:np.ndarray) -> float:
    # https://en.wikipedia.org/wiki/Pearson%27s_chi-squared_test
    assert(len(result_distribution)==len(expected_distribution))
    not_zero = np.where(expected_distribution != 0)[0]
    return stats.chisquare(result_distribution[not_zero], expected_distribution[not_zero]).statistic

def kullback_leibler_divergence(result_distribution:np.ndarray, expected_distribution:np.ndarray) -> float:
    # https://en.wikipedia.org/wiki/Kullback%E2%80%93Leibler_divergence
    assert(len(result_distribution)==len(expected_distribution))
    return stats.entropy(result_distribution, expected_distribution)

def bhattacharyya_difference(dist_1:np.ndarray, dist_2:np.ndarray) -> float:
    # https://en.wikipedia.org/wiki/Bhattacharyya_distance
    assert(len(dist_1)==len(dist_2))
    bc = np.sum(np.sqrt(dist_1*dist_2))
    if bc == 0:
        return np.inf
    return - np.log(bc)

def fidelity(dist_1:np.ndarray, dist_2:np.ndarray) -> float:
    return np.power(np.sum(np.sqrt(dist_1*dist_2)), 2)

def metric_diff(result_dist_1:np.ndarray, result_dist_2:np.ndarray, expected_dist:np.ndarray, metric:Callable[[np.ndarray, np.ndarray], float]) -> float:
    m_1 = metric(result_dist_1, expected_dist)
    m_2 = metric(result_dist_2, expected_dist)
    return m_1 - m_2

def same_max(result_dist:np.ndarray, expected_dist:np.ndarray) -> bool:
    return np.argmax(result_dist) == np.argmax(expected_dist)

def same_order(result_dist:np.ndarray, expected_dist:np.ndarray) -> bool:
    return (np.argsort(result_dist) == np.argsort(expected_dist)).all()

if __name__ == "__main__":
    a = np.array([0,0,1,0])
    b = np.array([0,1,0,0]) 
    c = np.array([1,1,1,1])/4 

    print("chi_square")
    print(chi_square(a, b))
    print(chi_square(a, c))
    print("kullback_leibler_divergence")
    print(kullback_leibler_divergence(a, b))
    print(kullback_leibler_divergence(a, c))
    print("bhattacharyya_difference")
    print(bhattacharyya_difference(a, b))
    print(bhattacharyya_difference(a, c))