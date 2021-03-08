from quantum_job import QuantumJob
from queue import Queue
from execution_handler.execution_handler import TranspilerExecution, BackendLookUp
from analyzer.backend_chooser import Backend_Data
from qiskit import IBMQ
import qiskit.ignis.verification.randomized_benchmarking as rb

if __name__ == "__main__":
    provider = IBMQ.load_account()
    backend_look_up = BackendLookUp(provider)
    output = Queue()
    te = TranspilerExecution(backend_look_up, output, 10)

    # number of qubits
    nQ = 2 
    rb_opts = {}
    #Number of Cliffords in the sequence
    rb_opts['length_vector'] = [1, 10, 20, 50, 75, 100, 125, 150, 175, 200]
    # Number of seeds (random sequences)
    rb_opts['nseeds'] = 10
    # Default pattern
    rb_opts['rb_pattern'] = [[0, 1]]


    shots = 8192

    backend_names = ['ibmq_qasm_simulator' , 'ibmq_athens', 'ibmq_santiago', 'ibmq_quito', 'ibmq_lima', 'ibmq_belem']
    # backend_names = ['ibmq_qasm_simulator']

    rb_circs, xdata = rb.randomized_benchmarking_seq(**rb_opts)

    backend_data_list = []
    backends = {}
    for backend_name in backend_names:
        backend = provider.get_backend(backend_name)
        backend_data = Backend_Data(backend)
        backend_data_list.append(backend_data)
        backends[backend_name] = {"backend":backend, "backend_data":backend_data}


    print("Start")

    for backend_data in backend_data_list:
        for rb_seed, rb_circ_seed in enumerate(rb_circs):
            for circ in rb_circ_seed:
                te.add_job(QuantumJob(circuit=circ, shots=shots, backend_data=backend_data))


    print("Added all jobs")

    def callback(future):
        print("Finished")
        print(future.result())

    while True:
        circuit, job = output.get()
        # print(job.id)