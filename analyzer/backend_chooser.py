import time
from typing import Any, Dict, List, Callable, Tuple, Optional
from qiskit import IBMQ, QuantumCircuit
from qiskit.providers.ibmq import least_busy
from qiskit import IBMQ
from qiskit.providers import Provider, Backend, backend


operational_filter = lambda x: x["operational"]
no_simulator_filter = lambda x: not x["simulator"]

class Backend_Chooser():

    def __init__(self, provider: Provider, update_interval: int = 60) -> None:
        self._provider = provider
        self._update_interval = update_interval
        self._backends = {}
        self._last_update = time.time()
        self._update_backends()

    def _update_backends(self):
        for b in self._provider.backends():
            self._backends[b.name()] = {"backend":b, "n_qubits":b.configuration().n_qubits, "operational":b.status().operational, "simulator":b.configuration().simulator, "pending_jobs":b.status().pending_jobs}

    def _check_update_backends(self):
        now = time.time()
        if self._last_update + self._update_interval < now:
            self._update_backends()
            self._last_update = now

    def get_backends(self, filters:Optional[Callable[[Dict], bool]] = None) -> Dict:
        self._check_update_backends()
        if filters == None:
            return self._backends
        value_filters = lambda x: filters(x[1])
        return dict(filter(value_filters, self._backends.items()))
    
    def get_backend_names(self, filters:Optional[Callable[[Dict], bool]] = None) -> List[str]:
        return self.get_backends(filters).keys()

    def get_least_busy(self, filters:Optional[Callable[[Backend], bool]] = None) -> Optional[Tuple[str, Dict]]:
        if filters == None:
            f = operational_filter
        else:
            f = lambda x: filters(x) and operational_filter(x)
        filtered_backends = self.get_backends(filters=f)
        if len(filtered_backends) == 0:
            return None
        least_busy = min(filtered_backends.items(), key=lambda x: x[1]["pending_jobs"])
        return least_busy 
        
    def get_least_busy_qubits(self, n_qubit:int) -> Tuple[str, Dict]:
        return self.get_least_busy(filters=lambda x: x["n_qubits"]>=n_qubit)

    def get_suitable_backends(self, circuit: QuantumCircuit, simulator: bool = False) -> List[Backend]:
        return self.get_backends(filters=lambda x: x.configuration().n_qubits >= circuit.num_qubits and x.configuration().simulator == simulator)

    def get_suitable_least_busy_backend(self, n_qubits: int, allow_simulator: bool = False):
        if allow_simulator:
            filter = lambda x: x.configuration().n_qubits >= n_qubits and x.status().operational
        else:
            filter = lambda x: x.configuration().n_qubits >= n_qubits and x.status().operational and x.configuration().simulator == False
        suitable_backends = self.get_name_backend_dict(filters=filter)
        if len(suitable_backends) == 0:
            return None 
        return least_busy(suitable_backends.values())



if __name__ == "__main__":
    IBMQ.load_account()
    provider = IBMQ.get_provider()
    bh =  Backend_Chooser(provider)
    # print(bh.get_backend_names(filters=lambda x: x.configuration().n_qubits >= 10 and not x.configuration().simulator))
    # print(bh.get_least_busy(filters=lambda x: not x.configuration().simulator))
    print(bh.get_backends_with_qubits(filters=lambda x: not x.configuration().simulator))
    # print(bh.get_backends_with_qubits())

    # Create a Quantum Circuit acting on the q register
    circuit = QuantumCircuit(2, 2)

    # Add a H gate on qubit 0
    circuit.h(0)

    # Add a CX (CNOT) gate on control qubit 0 and target qubit 1
    circuit.cx(0, 1)

    # Map the quantum measurement to the classical bits
    circuit.measure([0,1], [0,1])
    sb= bh.get_suitable_backends(circuit)
    print([b.name() for b in sb])
    print([b.status().to_dict() for b in sb])
    print(least_busy(sb))