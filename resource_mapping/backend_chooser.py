import copy
import time
from typing import Any, Dict, List, Callable, Tuple, Optional, Union
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
        self._config = config
        self._update_interval = update_interval
        self._backends = {}
        self._last_update = time.time()
        self._update_backends()

    def _backend_filter(self, backend:Union[Backend_Data,Tuple[str, Backend_Data]], filter_dict:Dict=None, filter_func:Callable[[Backend_Data],bool]=None) -> bool:
        if isinstance(backend, Tuple):
            _ , backend = backend
        if filter_dict is None:
            # use default config
            config = self._config
        else:
            # adapt default config with the given values
            config = copy.deepcopy(self._config)
            config.update(filter_dict)
        if filter_func is None:
            filter_func = lambda x:True

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
        return filter_func(backend)
        

    def _update_backends(self):
        for b in self._provider.backends():
            self._backends[b.name()] = Backend_Data(b)

    def _check_update_backends(self):
        now = time.time()
        if self._last_update + self._update_interval < now:
            self._update_backends()
            self._last_update = now

    def get_backends(self, filter_dict:Dict=None, filter_func:Optional[Callable[[Backend_Data],bool]] = None) -> Dict:
        self._check_update_backends()
        if filter_func == None:
            return self._backends
        backend_filter = lambda b: self._backend_filter(b, filter_dict, filter_func)
        return dict(filter(backend_filter, self._backends.items()))
    
    def get_backend_names(self, filter_dict:Dict=None, filter_func:Optional[Callable[[Backend_Data],bool]] = None) -> List[str]:
        return self.get_backends(filter_dict, filter_func).keys()

    def get_least_busy(self, filter_dict:Dict=None, filter_func:Optional[Callable[[Backend_Data],bool]] = None) -> Optional[Tuple[str, Dict]]:
        if filter_func is None:
            f = lambda x: x.operational and x.status_msg == "active"
        else:
            f = lambda x: filter_func(x) and x.operational and x.status_msg == "active"
        filtered_backends = self.get_backends(filter_dict=filter_dict, filter_func=f)
        if len(filtered_backends) == 0:
            return None
        backends_with_free_jobs = dict(filter(lambda backend: backend[1].active_jobs < backend[1].maximum_jobs, filtered_backends.items()))
        least_busy = min(backends_with_free_jobs.items(), key=lambda x: x[1].pending_jobs)
        return least_busy 
        



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