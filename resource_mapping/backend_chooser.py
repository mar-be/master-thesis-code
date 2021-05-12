import copy
import time
from typing import Callable, Dict, List, Optional, Tuple, Union

from qiskit.providers import Backend, Provider


class Backend_Data():
    """
    Caches the data locally for a remote backend
    """

    def __init__(self, backend: Backend) -> None:
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
    """
    Allows to query the local knowledgebase about the remote backends.
    It updates periodically the cached inforamtion.
    """

    def __init__(self, provider: Provider, config: Dict, update_interval: int = 60) -> None:
        self._provider = provider
        self._config = config
        self._update_interval = update_interval
        self._backends = {}
        self._last_update = time.time()
        self._update_backends()

    def _backend_filter(self, backend: Union[Backend_Data, Tuple[str, Backend_Data]], filter_dict: Dict = None, filter_func: Callable[[Backend_Data], bool] = None) -> bool:
        """Applies the filter_dict and the filter_func to the backend and evaluates it

        Args:
            backend (Union[Backend_Data,Tuple[str, Backend_Data]])
            filter_dict (Dict, optional): Dict that filters the backend. It has the same format as the backend_chooser part in the config file. If it is None, no filter is applied. Defaults to None.
            filter_func (Callable[[Backend_Data],bool], optional): Filter the backends via a callable that gets as input a Backend_Data object and outputs a bool. If it is None, no filter is applied. Defaults to None.

        Returns:
            bool: Return True, if the backend is compliant with the filters
        """
        if isinstance(backend, Tuple):
            _, backend = backend
        if filter_dict is None:
            # use default config
            config = self._config
        else:
            # adapt default config with the given values
            config = copy.deepcopy(self._config)
            config.update(filter_dict)
        if filter_func is None:
            def filter_func(x): return True

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
        """
        Cache all information about the remote backends
        """
        for b in self._provider.backends():
            self._backends[b.name()] = Backend_Data(b)

    def _check_update_backends(self):
        """Check if the local knowledge base about the remote backends needs an update
        """
        now = time.time()
        if self._last_update + self._update_interval < now:
            self._update_backends()
            self._last_update = now

    def get_backends(self, filter_dict: Dict = None, filter_func: Optional[Callable[[Backend_Data], bool]] = None) -> Dict:
        """Query the local knowledge base about the remote backends

        Args:
            filter_dict (Dict, optional): Dict that filters the backends. It has the same format as the backend_chooser part in the config file. If it is None, no filter is applied. Defaults to None.
            filter_func (Optional[Callable[[Backend_Data],bool]], optional): Filter the backends via a callable that gets as input a Backend_Data object and outputs a bool. If it is None, no filter is applied. Defaults to None.

        Returns:
            Dict: key is the name of the backend, value is a Backend_Data object
        """
        self._check_update_backends()
        if filter_func == None:
            return self._backends

        def backend_filter(b): return self._backend_filter(
            b, filter_dict, filter_func)
        return dict(filter(backend_filter, self._backends.items()))

    def get_backend_names(self, filter_dict: Dict = None, filter_func: Optional[Callable[[Backend_Data], bool]] = None) -> List[str]:
        """Query the local knowledge base about the remote backends

        Args:
            filter_dict (Dict, optional): Dict that filters the backends. It has the same format as the backend_chooser part in the config file. If it is None, no filter is applied. Defaults to None.
            filter_func (Optional[Callable[[Backend_Data],bool]], optional): Filter the backends via a allable that gets as input a Backend_Data object and outputs a bool. If it is None, no filter is applied. Defaults to None.

        Returns:
            List[str]: list of backend names
        """
        return self.get_backends(filter_dict, filter_func).keys()

    def get_least_busy(self, filter_dict: Dict = None, filter_func: Optional[Callable[[Backend_Data], bool]] = None) -> Optional[Tuple[str, Dict]]:
        """Return the least busy remote backend from the local knowledge base 

        Args:
            filter_dict (Dict, optional): Dict that filters the backends. It has the same format as the backend_chooser part in the config file. If it is None, no filter is applied. Defaults to None.
            filter_func (Optional[Callable[[Backend_Data],bool]], optional): Filter the backends via a callable that gets as input a Backend_Data object and outputs a bool. If it is None, no filter is applied. Defaults to None.

        Returns:
            Optional[Tuple[str, Dict]]: Tuple containing the backend name and a Backend_Data object. Return None if no backend is available.
        """
        if filter_func is None:
            def f(x): return x.operational and x.status_msg == "active"
        else:
            def f(x): return filter_func(
                x) and x.operational and x.status_msg == "active"
        filtered_backends = self.get_backends(
            filter_dict=filter_dict, filter_func=f)
        if len(filtered_backends) == 0:
            return None
        backends_with_free_jobs = dict(filter(
            lambda backend: backend[1].active_jobs < backend[1].maximum_jobs, filtered_backends.items()))
        least_busy = min(backends_with_free_jobs.items(),
                         key=lambda x: x[1].pending_jobs)
        return least_busy
