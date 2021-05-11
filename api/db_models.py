
from flask_mongoengine import Document
from mongoengine.fields import DictField, IntField, StringField

from qiskit import QuantumCircuit

from quantum_execution_job import QuantumExecutionJob


class Task(Document):
    qasm = StringField(required=True)
    shots = IntField(min_value=0, default=8192)
    qjob_id = StringField(null=True)
    status = StringField(default="created")
    config = DictField(default={})
    result = DictField(default={})

    @property
    def id_str(self):
        return str(self.id)

    def to_dict(self):
        d = {"id":self.id_str, "qasm":self.qasm, "status":self.status, "shots":self.shots, "config":self.config}
        if self.result:
            d["result"] = self.result
        return d

    def update_results(self, job:QuantumExecutionJob):
        self.result = job.result_prob

    def create_qjob(self):
        qjob = QuantumExecutionJob(QuantumCircuit.from_qasm_str(self.qasm), shots=self.shots, config=self.config)
        self.qjob_id = qjob.id
        return qjob
