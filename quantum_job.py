from typing import Any, Dict, Optional
from qiskit import QuantumCircuit
from qiskit.result import Result
from uuid import uuid4
from enum import Enum

class Modification_Type(Enum):
    none = 0
    aggregation = 1
    partition = 2

class QuantumJob():

    def __init__(self, circuit:QuantumCircuit, type:Modification_Type=Modification_Type.none, **kwargs) -> None:
        self.id = uuid4().hex
        self.circuit = circuit
        self.type = type
        self.result:Optional[Result] = None
        self.__dict__.update(kwargs)

    

if __name__ == "__main__":
    vJob = QuantumJob(None, test = "test")

    print(vJob.test)
    vJob.hallo = 1234
    print(vJob.hallo)
    print(vJob.__dict__)