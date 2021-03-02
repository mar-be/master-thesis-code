from typing import Any, Dict, Optional
from qiskit import QuantumCircuit
from qiskit.result import Result
from uuid import uuid4
from enum import Enum

class Status(Enum):
    created = 0
    running = 1
    failed = 2
    deleted = 3
    done = 4

class Modification_Type(Enum):
    none = 0
    aggregation = 1
    partition = 2

class QuantumJob():

    def __init__(self, circuit:QuantumCircuit, shots:int, type:Modification_Type=Modification_Type.none, **kwargs) -> None:
        self.id = uuid4().hex
        self.circuit = circuit
        self.type = type
        self.shots = shots
        self._result:Optional[Result] = None
        self.result_prob:Optional[Dict] = None
        self.__dict__.update(kwargs)

    @property
    def result(self) -> Optional[Result]:
        return self._result

    @result.setter
    def result(self, result:Optional[Result]):
        if result:
            self._result = result
            cnts = result.data()['counts']
            self.result_prob = dict({key:value/self.shots for key, value in cnts.items()})
        else:
            self._result = None


class QuantumTask(QuantumJob):
    def __init__(self, circuit: QuantumCircuit, shots: int, type: Modification_Type=Modification_Type.none, **kwargs) -> None:
        self.status: Status = Status.created
        QuantumJob.__init__(self, circuit, shots, type, **kwargs) 
    
    @classmethod
    def create(cls, task_dict:Dict):
    
        qasm = task_dict["qasm"]
        shots = task_dict["shots"]
        circuit = QuantumCircuit.from_qasm_str(qasm)

        return cls(circuit, shots)

    def to_dict(self):
        d = {"id":self.id, "qasm":self.circuit.qasm(), "status":self.status.name, "shots":self.shots}
        if self.result_prob:
            d["result"] = self.result_prob
        return d


    

if __name__ == "__main__":
    vJob = QuantumJob(None, test = "test")

    print(vJob.test)
    vJob.hallo = 1234
    print(vJob.hallo)
    print(vJob.__dict__)