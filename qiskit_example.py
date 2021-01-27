from quantum_ciruit_object import Quantum_Job, session
from execution_handler.job_monitor import Job_Monitor
import numpy as np
from qiskit import(
  QuantumCircuit,
  execute,
  IBMQ
  )
from qiskit.circuit.classicalregister import ClassicalRegister
from qiskit.circuit.quantumregister import AncillaRegister, QuantumRegister
from qiskit.converters import circuit_to_dag
from qiskit.circuit.random import random_circuit
from aggregator import aggregate_q_jobs, split_results
from partitioner import karger_algorithm

import networkx as nx


# IBMQ.save_account('f5865210c4c93e8a0b5230c96a2cc402ad8c603c92641a1655b9f8c729ebf3ab4899db914dcd6aa8b75cd0849e34d5fc0f74adcd856d0d09da6aafc217d86bd4')
provider = IBMQ.load_account()
# backend = provider.get_backend('ibmq_qasm_simulator')
backend = provider.get_backend('ibmq_santiago')

# Create a Quantum Circuit acting on the q register
circuit = QuantumCircuit(2, 2)

# Add a H gate on qubit 0
circuit.h(0)

# Add a CX (CNOT) gate on control qubit 0 and target qubit 1
circuit.cx(0, 1)

# Map the quantum measurement to the classical bits
circuit.measure([0,1], [0,1])

# Create a Quantum Circuit acting on the q register
circuit_2 = QuantumCircuit(2, 2)

# Add a H gate on qubit 0
circuit_2.h(0)

# Add a CX (CNOT) gate on control qubit 0 and target qubit 1
circuit_2.cx(0, 1)


# Map the quantum measurement to the classical bits
circuit_2.measure([0,1], [0,1])

print(circuit)
print(circuit_2)

q_job = Quantum_Job(circuit)
q_job2 = Quantum_Job(circuit_2)

session.add(q_job)
session.add(q_job2)
session.commit()

agg_job = aggregate_q_jobs([q_job, q_job2])

agg_circuit = agg_job.circuit

print(agg_circuit)
# print(agg_circuit.num_connected_components())

# Execute the circuit on the qasm simulator
job_1 = execute(circuit, backend, shots=8192)
job_2 = execute(circuit_2, backend, shots=8192)
job = execute(agg_circuit, backend, shots=8192)

agg_job.qiskit_job_id = job.job_id()

res = split_results(job.result(), agg_job)

print("Result 1 agg:")
print(res[0])
print("Result 2 agg:")
print(res[1])
print("\n")
print("Result 1:")
print(job_1.result())
print("Result 2:")
print(job_2.result())

# monitor = Job_Monitor(1)

# monitor.add(job)
# monitor.add(job_1)
# monitor.add(job_2)

# Grab results from the job
# result = job.result()

# # Returns counts
# counts = result.get_counts(agg_circuit)
# print("\nTotal count for 00 and 11 are:",counts)

# Draw the circuit
circuit.draw()

