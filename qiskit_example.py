import numpy as np
from qiskit import(
  QuantumCircuit,
  execute,
  IBMQ
  )
from qiskit.converters import circuit_to_dag
from aggregator import aggregate
from partitioner import karger_algorithm

import networkx as nx


# IBMQ.save_account('f5865210c4c93e8a0b5230c96a2cc402ad8c603c92641a1655b9f8c729ebf3ab4899db914dcd6aa8b75cd0849e34d5fc0f74adcd856d0d09da6aafc217d86bd4')
provider = IBMQ.load_account()
backend = provider.get_backend('ibmq_qasm_simulator')


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

# Map the quantum measurement to the classical bits
circuit_2.measure([0,1], [0,1])

print(circuit)
print(circuit_2)
dag = circuit_to_dag(circuit)
for node in dag.longest_path():
    print(node.name)
dag.draw()
dag_nx = dag.to_networkx()
print([node.name for node in dag_nx.nodes])
print(dag_nx)

cut = karger_algorithm(dag_nx, 2)
for (u, v, w) in cut.edges:
    print((u.name, u._node_id), (v.name, v._node_id))
# mapping = {node:node.name + ":" + str(node._node_id) for node in dag_nx.nodes}
# print(mapping)
# dag_nx_relabeled = nx.relabel_nodes(dag_nx, mapping)


agg_circuit = aggregate([circuit, circuit_2])

print(agg_circuit)
print(agg_circuit.num_connected_components())

# Execute the circuit on the qasm simulator
job = execute(agg_circuit, backend, shots=1000)

# Grab results from the job
result = job.result()

# Returns counts
counts = result.get_counts(agg_circuit)
print("\nTotal count for 00 and 11 are:",counts)

# Draw the circuit
circuit.draw()

