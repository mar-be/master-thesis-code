from qiskit import QuantumCircuit
import uuid
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String
import sqlalchemy.types as types

class QCircuit(types.TypeDecorator):
    

    def process_bind_param(self, value:QuantumCircuit, dialect):
        return value.qasm()

    def process_result_value(self, value:str, dialect):
        return QuantumCircuit.from_qasm_str(value)


# declarative base class
Base = declarative_base()

class QC_Object(Base):

    __tablename__ = 'qc_object'

    id = Column(Integer, primary_key=True)
    circuit = Column(QCircuit, nullable=False)



    def __init__(self,  circuit:QuantumCircuit) -> None:
        self.id = uuid.uuid4()
        self.circuit = circuit

    @classmethod
    def from_qasm(cls, quasm:str):
        circuit = QuantumCircuit.from_qasm_str(quasm)
        return cls(circuit)



if __name__ == "__main__":

    # Create a Quantum Circuit acting on the q register
    circuit = QuantumCircuit(2, 2)

    # Add a H gate on qubit 0
    circuit.h(0)

    # Add a CX (CNOT) gate on control qubit 0 and target qubit 1
    circuit.cx(0, 1)

    # Map the quantum measurement to the classical bits
    circuit.measure([0,1], [0,1])

    qc_obj = QC_Object.from_qasm(circuit.qasm())

    print(qc_obj.id)
    print(qc_obj.circuit.qasm())