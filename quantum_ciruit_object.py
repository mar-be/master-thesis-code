from qiskit import QuantumCircuit
from sqlalchemy.ext.declarative import declarative_base
import sqlalchemy.types as types
from sqlalchemy import create_engine, Column
from sqlalchemy.orm import sessionmaker


# declarative base class
Base = declarative_base()
engine = create_engine('sqlite:///foo.db')
session = sessionmaker(engine)()


class QC_Object(Base):

    __tablename__ = 'qc_object'

    id = Column(types.Integer, primary_key=True)
    _qasm = Column("qasm", types.String, nullable=False)

    def __init__(self,  circuit:QuantumCircuit) -> None:
        self.circuit = circuit

    @property
    def circuit(self):
        if not hasattr(self, '_circuit') and self._qasm:
            self._circuit = QuantumCircuit.from_qasm_str(self._qasm)
        return self._circuit
        

    @circuit.setter
    def circuit(self, value):
        self._circuit = value
        self._qasm = self._circuit.qasm()

    @classmethod
    def from_qasm(cls, qasm:str):
        circuit = QuantumCircuit.from_qasm_str(qasm)
        return cls(circuit)



        

if __name__ == "__main__":
    QC_Object.metadata.create_all(engine)

    # Create a Quantum Circuit acting on the q register
    circuit = QuantumCircuit(2, 2)

    # Add a H gate on qubit 0
    circuit.h(0)

    # Add a CX (CNOT) gate on control qubit 0 and target qubit 1
    circuit.cx(0, 1)

    # Map the quantum measurement to the classical bits
    circuit.measure([0,1], [0,1])

    qc_obj = QC_Object.from_qasm(circuit.qasm())

    session.add(qc_obj)
    session.commit()

    print(qc_obj.id)
    print(qc_obj.circuit.qasm())

    query_obj = session.query(QC_Object).first()
    qc = query_obj.circuit
    print(qc.qasm())