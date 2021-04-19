
import math

from qiskit.circuit.library.grover_operator import GroverOperator
from quantum_circuit_generator.generators import gen_BV, gen_adder, gen_hwea, gen_uccsd, gen_supremacy
from qiskit.circuit.quantumcircuit import QuantumCircuit
from qiskit.circuit.random import random_circuit
from qiskit.circuit.library import QFT

from qiskit.converters import circuit_to_dag, dag_to_circuit

def gen_grover(n_qubits):    
    oracle = QuantumCircuit(n_qubits,name='q')
    for q in range(n_qubits):
        oracle.h(q)
    oracle.cz(0,n_qubits-1)
    oracle.x(n_qubits-1)
    return GroverOperator(oracle, insert_barriers=True, name='q')

def grover(n_qubits, n_circuits):
    return [gen_grover(n_qubits) for i in range(n_circuits)], n_circuits


def random_circuits(n_qubits, n_circuits, depth=5):
    return [random_circuit(n_qubits, depth, measure=False) for i in range(n_circuits)], n_circuits

def adder_circuits(n_qubits):
    nbits=int((n_qubits-2)/2)
    n_circuits = 2**(2*nbits)
    return [gen_adder(nbits=nbits, a=a, b=b) for a in range(2**nbits) for b in range(2**nbits)], n_circuits

def adder_circuit_a_b(n_qubits, n_circuits, a=0, b=1):
    if n_qubits % 2 == 0:
        nbits=int((n_qubits-2)/2)
        return [gen_adder(nbits=nbits, a=a, b=b) for i in range(n_circuits)], n_circuits
    else:
        nbits=int((n_qubits-1)/2)
        circ = gen_adder(nbits=nbits, a=a, b=b)
        dag = circuit_to_dag(circ)
        wire = dag.wires[n_qubits]
        nodes = list(dag.nodes_on_wire(wire, only_ops=True))
        for node in nodes:
            dag.remove_op_node(node)
        circ = dag_to_circuit(dag)
        circ = QuantumCircuit.from_qasm_str(circ.qasm().replace(f"qreg q0[{n_qubits+1}];", f"qreg q0[{n_qubits}];"))
        return [circ for i in range(n_circuits)], n_circuits


def growing_depth(n_qubits, n_circuits):
    circuits = []
    circ = QuantumCircuit(n_qubits)
    for i in range(n_circuits):
        circ = random_circuit(n_qubits, 1, measure=False).combine(circ)
        circuits.append(circ)
    return circuits, n_circuits

def hwea(n_qubits, n_circuits, depth=5):
    return [gen_hwea(n_qubits, depth) for i in range(n_circuits)], n_circuits

def uccsd(n_qubits, n_circuits):
    return [gen_uccsd(n_qubits) for i in range(n_circuits)], n_circuits

def qft(n_qubits, n_circuits):
    return [QFT(num_qubits=n_qubits, approximation_degree=0, do_swaps=False) for i in range(n_circuits)], n_circuits

def aqft(n_qubits, n_circuits):
    approximation_degree=int(math.log(n_qubits,2)+2)
    return [QFT(num_qubits=n_qubits, approximation_degree=n_qubits-approximation_degree,do_swaps=False) for i in range(n_circuits)], n_circuits

def supremacy_linear(n_qubits, n_circuits, depth=8):
    # return [gen_supremacy(1, n_qubits, depth, regname='q') for i in range(n_circuits)], n_circuits
    # TODO remove hardcoded circuit
    circ = QuantumCircuit.from_qasm_str("OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[5];\nh q[0];\nh q[1];\nh q[2];\nh q[3];\nh q[4];\ncz q[0],q[1];\nt q[2];\nt q[3];\nt q[4];\nrx(pi/2) q[0];\nrx(pi/2) q[1];\ncz q[1],q[2];\nt q[0];\nry(pi/2) q[1];\nrx(pi/2) q[2];\ncz q[2],q[3];\nt q[1];\nrx(pi/2) q[2];\nrx(pi/2) q[3];\ncz q[3],q[4];\nt q[2];\nry(pi/2) q[3];\nry(pi/2) q[4];\nh q[0];\nh q[1];\nh q[2];\nh q[3];\nh q[4];\n")
    return [circ for i in range(n_circuits)], n_circuits

def gen_secret(n_qubit):
    num_digit = n_qubit-1
    num = 2**num_digit-1
    num = bin(num)[2:]
    num_with_zeros = str(num).zfill(num_digit)
    return num_with_zeros

def bv(n_qubits, n_circuits):
    return [gen_BV(gen_secret(n_qubits), barriers=False, regname='q') for i in range(n_circuits)], n_circuits

def circ_gen(circuit_type, n_qubits, n_circuits):
    if circuit_type == "random":
        circuits, n_circuits = random_circuits(n_qubits, n_circuits)
    elif circuit_type == "adder":
        circuits, n_circuits = adder_circuit_a_b(n_qubits, n_circuits)
    elif circuit_type == "growing_depth":
        circuits, n_circuits = growing_depth(n_qubits, n_circuits)
    elif circuit_type == "hwea":
        circuits, n_circuits = hwea(n_qubits, n_circuits)
    elif circuit_type == "uccsd":
        circuits, n_circuits = uccsd(n_qubits, n_circuits)
    elif circuit_type == "aqft":
        circuits, n_circuits = aqft(n_qubits, n_circuits)
    elif circuit_type == "qft":
        circuits, n_circuits = qft(n_qubits, n_circuits)
    elif circuit_type == 'supremacy_linear':
        circuits, n_circuits = supremacy_linear(n_qubits, n_circuits)
    elif circuit_type == 'bv':
        circuits, n_circuits = bv(n_qubits, n_circuits)
    elif circuit_type == 'grover':
        circuits, n_circuits = grover(n_qubits, n_circuits)
    else:
        raise ValueError("Inappropiate circuit_type")
    return circuits, n_circuits
