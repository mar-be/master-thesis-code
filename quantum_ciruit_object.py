from typing import List
from qiskit import QuantumCircuit
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql.schema import ForeignKey
import sqlalchemy.types as types
from sqlalchemy import create_engine, Column
from sqlalchemy.orm import backref, relationship, sessionmaker


# declarative base class
Base = declarative_base()
engine = create_engine('sqlite:///foo.db')
session = sessionmaker(engine)()

class Modification(Base):

    __tablename__ = "qc_modification"
    id = Column(types.Integer, primary_key=True)
    type = Column(types.String, nullable=False)

    input_circuit = relationship("QC_Object", backref="modification_input", foreign_keys="QC_Object.input_modification_id")
    output_circuit = relationship("QC_Object", backref="modification_output", foreign_keys="QC_Object.output_modification_id")


class QC_Object(Base):

    __tablename__ = 'qc_object'

    id = Column(types.Integer, primary_key=True)
    _qasm = Column("qasm", types.String, nullable=False)
    input_modification_id = Column(types.Integer, ForeignKey("qc_modification.id"))
    output_modification_id = Column(types.Integer, ForeignKey("qc_modification.id"))
    

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
    Base.metadata.create_all(engine)

    # Create a Quantum Circuit acting on the q register
    circuit = QuantumCircuit(2, 2)

    # Add a H gate on qubit 0
    circuit.h(0)

    # Add a CX (CNOT) gate on control qubit 0 and target qubit 1
    circuit.cx(0, 1)

    # Map the quantum measurement to the classical bits
    circuit.measure([0,1], [0,1])

    qc_obj = QC_Object.from_qasm(circuit.qasm())

    # Create a Quantum Circuit acting on the q register
    circuit_2 = QuantumCircuit(2, 2)

    # Add a H gate on qubit 0
    circuit_2.h(0)

    # Map the quantum measurement to the classical bits
    circuit_2.measure([0,1], [0,1])


    qc_obj_2 = QC_Object(circuit_2)
    mod = Modification()
    mod.input_circuit.append(qc_obj)
    mod.input_circuit.append(qc_obj_2)
    mod.output_circuit.append(qc_obj_2)
    mod.type = "test"

    session.add(qc_obj)
    session.add(qc_obj_2)

    session.commit()


    print(qc_obj.id)
    print(qc_obj.circuit.qasm())

    query_obj = session.query(QC_Object).first()
    qc = query_obj.circuit
    print(qc.qasm())