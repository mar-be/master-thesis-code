from typing import Dict
import numpy as np

def counts_to_probability(counts:Dict, n_qubits:int) -> np.ndarray:
    shots = sum(counts.values())
    prob_dist = np.zeros(2**n_qubits)
    for key, value in counts.items():
        if isinstance(key, int):
            pass
        elif isinstance(key, str):
            if key.startswith("0x"):
                key = int(key, 16)
            elif key.startswith("0") or key.startswith("1"):
                key = int(key, 2)
            else:
                raise ValueError("String could not be decoded")
        else:
            raise TypeError("Type has to be either integer or string")
        prob_dist[key] = value/shots
    return prob_dist



def sv_to_probability(statevector:np.ndarray) -> np.ndarray:
    return np.vectorize(_complex_length)(statevector)

def _complex_length(complex_number:complex) -> float:
    return np.power(complex_number.real, 2) + np.power(complex_number.imag, 2)

def _round(number:np.float, tol=None):
    if not tol:
        tol = np.float=np.finfo(np.float).eps
    if abs(number) < tol:
        return 0.0
    elif abs(number-1) < tol:
        return 1.0
    else:
        return number

def round(array:np.ndarray, tol=None)-> np.ndarray:
    if tol:
        return np.vectorize(lambda x :_round(x, tol))(array)
    else:
        return np.vectorize(_round)(array)

def reject_outliers(data, m = 3.):
    d = np.abs(data - np.median(data))
    mdev = np.median(d)
    s = d/mdev if mdev else 0.
    bool_array = s<m
    return data[bool_array], np.where(bool_array)[0], bool_array

if __name__ == "__main__":
    data_points = np.array([1, 12, 2, 200, 7, 8])
    data, index, bool_array = reject_outliers(data_points)
    print(data)
    print(index)
    print(bool_array)