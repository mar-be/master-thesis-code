from typing import List
from networkx.generators.classic import balanced_tree
from qiskit import QuantumCircuit
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql.schema import ForeignKey
import sqlalchemy.types as types
from sqlalchemy import create_engine, Column, Table
from sqlalchemy.orm import backref, relationship, sessionmaker
import enum
import json


# declarative base class
Base = declarative_base()
engine = create_engine('sqlite:///foo.db')
session = sessionmaker(engine)()

modification_link = Table("modification_link", Base.metadata,
    Column("input_id", types.Integer, ForeignKey("quantum_job.id"), primary_key=True),
    Column("output_id", types.Integer, ForeignKey("quantum_job.id"), primary_key=True)
)

class Modification_Type(enum.Enum):
    none = 0
    aggregation = 1
    partition = 2

class Dict(types.TypeDecorator):
    impl = types.String

    def process_bind_param(self, value, dialect):
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        return json.loads(value)

class Quantum_Job(Base):

    __tablename__ = 'quantum_job'

    id = Column(types.Integer, primary_key=True)
    _qasm = Column("qasm", types.String, nullable=False)
    mod_type = Column(types.Enum(Modification_Type))
    mod_info = Column(Dict())
    qiskit_job_id = Column(types.String)


    output_jobs = relationship("Quantum_Job", secondary="modification_link", primaryjoin="Quantum_Job.id==modification_link.c.input_id", secondaryjoin="Quantum_Job.id==modification_link.c.output_id", backref="input_jobs")
    

    def __init__(self,  circuit:QuantumCircuit, mod_type:Modification_Type = Modification_Type.none) -> None:
        self.circuit = circuit
        self.qiskit_job_id = None
        self.mod_type = mod_type
        self.mod_info = {}

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


    

Base.metadata.create_all(engine)

if __name__ == "__main__":

    # Create a Quantum Circuit acting on the q register
    circuit = QuantumCircuit(2, 2)

    # Add a H gate on qubit 0
    circuit.h(0)

    # Add a CX (CNOT) gate on control qubit 0 and target qubit 1
    circuit.cx(0, 1)

    # Map the quantum measurement to the classical bits
    circuit.measure([0,1], [0,1])

    qc_obj = Quantum_Job.from_qasm(circuit.qasm())

    # Create a Quantum Circuit acting on the q register
    circuit_2 = QuantumCircuit(2, 2)

    # Add a H gate on qubit 0
    circuit_2.h(0)

    # Map the quantum measurement to the classical bits
    circuit_2.measure([0,1], [0,1])


    qc_obj_2 = Quantum_Job(circuit_2)
    qc_obj_2.input_jobs.append(qc_obj)

    session.add(qc_obj)
    session.add(qc_obj_2)

    session.commit()

    print(qc_obj.output_jobs)

    print(qc_obj.id)
    print(qc_obj.circuit.qasm())

    query_obj = session.query(Quantum_Job).first()
    qc = query_obj.circuit
    print(qc.qasm())