from typing import Any, Dict, List, Callable, Tuple, Optional
from qiskit import IBMQ, QuantumCircuit
from qiskit.providers.ibmq import least_busy
from qiskit import IBMQ
from qiskit.providers import Provider, Backend, backend


class Backend_Chooser():

    def __init__(self, provider: Provider) -> None:
        self.provider = provider

    def get_backends(self, filters:Optional[Callable[[Backend], bool]] = None) -> List[Backend]:
        return self.provider.backends(filters=filters)
    
    def get_backend_names(self, filters:Optional[Callable[[Backend], bool]] = None) -> List[str]:
        return [b.name() for b in self.get_backends(filters=filters)]

    def get_name_backend_dict(self, filters:Optional[Callable[[Backend], bool]] = None) -> Dict[str, Backend]:
        return {b.name():b for b in self.get_backends(filters=filters)}

    def get_backends_with_qubits(self, filters:Optional[Callable[[Backend], bool]] = None) -> List[Tuple[Backend, int]]:
        return [(b.name(), b.configuration().n_qubits) for b in self.get_backends(filters=filters)]

    def get_least_busy(self, filters:Optional[Callable[[Backend], bool]] = None) -> str:
        return least_busy(self.get_backends(filters=filters))

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