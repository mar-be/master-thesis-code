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