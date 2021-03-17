from typing import Dict, Optional
from qiskit import IBMQ
from qiskit.providers.ibmq.accountprovider import AccountProvider
import logger

log = logger.get_logger(__name__)


def get_provider(ibmq_config:Optional[Dict]=None) -> Optional[AccountProvider]:
    """Authenticate against IBM Quantum Experience.
    Either use the specified token in the config or stored token.

    Args:
        ibmq_config (Optional[Dict], optional): If the IBMQ config dict is not None and it conatins a token, the method uses this token. Defaults to None.

    Returns:
        Optional[AccountProvider]: a authenticated session via a Provider object
    """    
    if not ibmq_config is None and "token" in ibmq_config.keys():
        provider = IBMQ.enable_account(ibmq_config["token"])
    else:
        provider = IBMQ.load_account()
    log.info("IBMQ authentification sucessful")
    return provider
