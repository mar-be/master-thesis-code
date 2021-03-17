import copy
import time
from typing import Any, Dict, List, Callable, Tuple, Optional
from qiskit import IBMQ, QuantumCircuit
from qiskit.providers.ibmq import least_busy
from qiskit import IBMQ
from qiskit.providers import Provider, Backend
from qiskit.providers.ibmq.ibmqbackend import IBMQBackend



class Backend_Data():

    def __init__(self, backend:Backend) -> None:
        self.name = backend.name()
        self.n_qubits = backend.configuration().n_qubits
        self.operational = backend.status().operational
        self.simulator = backend.configuration().simulator
        self.pending_jobs = backend.status().pending_jobs
        self.active_jobs = backend.job_limit().active_jobs
        self.maximum_jobs = backend.job_limit().maximum_jobs
        self.status_msg = backend.status().status_msg
        # only available by real QPUs
        try:
            self.quantum_volume = backend.configuration().quantum_volume
        except AttributeError:
            pass

    def __str__(self):
        return str(self.__dict__)


class Backend_Chooser():

    def __init__(self, provider: Provider, config:Dict, update_interval: int = 60) -> None:
        self._provider = provider
        self._config = config["backend_chooser"]
        self._update_interval = update_interval
        self._backends = {}
        self._last_update = time.time()
        self._update_backends()

    def _config_filter(self, backend:Backend_Data, filters:Dict=None) -> bool:
        if filters is None:
            # use default config
            config = self._config
        else:
            # adapt default config with the given values
            config = copy.deepcopy(self._config)
            config.update(filters)

        if backend.name in config["backend_black_list"]:
            return False
        if len(config["backend_white_list"]) > 0 and backend.name not in config["backend_white_list"]:
            return False
        if not config["allow_simulator"] and backend.simulator:
            return False
        if not config["number_of_qubits"]["min"] is None and config["number_of_qubits"]["min"] > backend.n_qubits:
            return False
        if not config["number_of_qubits"]["max"] is None and config["number_of_qubits"]["max"] < backend.n_qubits:
            return False
        if hasattr(backend, "quantum_volume"):
            if not config["quantum_volume"]["min"] is None and config["quantum_volume"]["min"] > backend.quantum_volume:
                return False
            if not config["quantum_volume"]["max"] is None and config["quantum_volume"]["max"] < backend.quantum_volume:
                return False
        return True
        

    def _update_backends(self):
        for b in self._provider.backends():
            self._backends[b.name()] = Backend_Data(b)

    def _check_update_backends(self):
        now = time.time()
        if self._last_update + self._update_interval < now:
            self._update_backends()
            self._last_update = now

    def get_backends(self, filters:Optional[Callable[[Dict], bool]] = None) -> Dict:
        self._check_update_backends()
        if filters == None:
            return self._backends
        value_filters = lambda x: filters(x[1])
        return dict(filter(value_filters, self._backends.items()))
    
    def get_backend_names(self, filters:Optional[Callable[[Dict], bool]] = None) -> List[str]:
        return self.get_backends(filters).keys()

    def get_least_busy(self, filters:Optional[Callable[[Backend], bool]] = None) -> Optional[Tuple[str, Dict]]:
        if filters == None:
            f = lambda x: x.operational and x.status_msg == "active"
        else:
            f = lambda x: filters(x) and x.operational and x.status_msg == "active"
        filtered_backends = self.get_backends(filters=f)
        if len(filtered_backends) == 0:
            return None
        backends_with_free_jobs = dict(filter(lambda backend: backend[1].active_jobs < backend[1].maximum_jobs, filtered_backends.items()))
        least_busy = min(backends_with_free_jobs.items(), key=lambda x: x[1].pending_jobs)
        return least_busy 
        
    def get_least_busy_qubits(self, n_qubit:int) -> Tuple[str, Dict]:
        return self.get_least_busy(filters=lambda x: x.n_qubits>=n_qubit)




if __name__ == "__main__":
    IBMQ.load_account()
    provider = IBMQ.get_provider()
    bc =  Backend_Chooser(provider)
    backend_name, backend_data = bc.get_least_busy(filters=lambda x: x.n_qubits>=5 and not x.simulator and x.quantum_volume >= 16)
    print(backend_name)
    print(backend_data)
    # print([b.name() for b in sb])
    # print([b.status().to_dict() for b in sb])
    # print(least_busy(sb))