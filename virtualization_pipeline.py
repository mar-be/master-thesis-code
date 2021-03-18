from virtualization_layer import Virtualization_Layer

from qiskit import IBMQ
from qiskit.circuit.random.utils import random_circuit

import logger

from quantum_job import QuantumJob
import config.load_config as cfg
import ibmq_account

if __name__ == "__main__":

    config = cfg.load_or_create()
    logger.set_log_level_from_config(config)
    log = logger.get_logger(__name__)
    provider = ibmq_account.get_provider(config)

    vl = Virtualization_Layer(provider, config)

    input = vl.input
    output = vl.output

    vl.start()

    input.put(QuantumJob(random_circuit(6, 5, 2, measure=True), shots=10000))
    input.put(QuantumJob(random_circuit(5, 5, 2, measure=True), shots=10000))
    input.put(QuantumJob(random_circuit(5, 5, 2, measure=True), shots=10000))
    input.put(QuantumJob(random_circuit(2, 5, 2, measure=True), shots=10000))
    input.put(QuantumJob(random_circuit(2, 5, 2, measure=True), shots=10000))

    i = 0
    while True:
        job = output.get() 
        log.info(job.result_prob)
        i += 1
