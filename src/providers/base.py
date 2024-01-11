import logging
logger = logging.getLogger(__name__)

from typing import List
from enum import StrEnum, auto

from node import ActionFlag, Node

class ProviderBaseException(Exception):
    """Raised when something bad happened in autoscale main"""

class ProviderStatus(StrEnum):
    RUNNING = auto()
    SHUTDOWN = auto()

class ProviderBase:
    def __init__(self, managed_nodes: List[Node]):
        self.managed_nodes = managed_nodes

    def get_nodes_status(self) -> dict[str, ProviderStatus]:
        raise NotImplementedError

    def sync_status(self) -> dict[str, ProviderStatus]:
        raise NotImplementedError

    def _get_changes(self, nodes_state: dict[str, ProviderStatus]):
        nodes_to_start = []
        nodes_to_stop = []
        for n in self.managed_nodes:
            match (n.flag, nodes_state.get(n.name)):
                case [ActionFlag.TO_START, ProviderStatus.RUNNING]:
                    logger.warning(f"Autoscaler request to start node={n.name} but node is already RUNNING. Ignoring Autoscaler requests.")
                    n.flag = None
                case [ActionFlag.TO_START, ProviderStatus.SHUTDOWN]:
                    nodes_to_start.append(n)
                case [ActionFlag.TO_DELETE, ProviderStatus.RUNNING]:
                    nodes_to_stop.append(n)
                case [ActionFlag.TO_DELETE, ProviderStatus.SHUTDOWN]:
                    logger.warning(f"Autoscaler request to stop node={n.name} but node is already SHUTDOWN. Ignoring Autoscaler requests.")
                    n.flag = None
                case [None, _]:
                    pass
                case _:
                    raise ProviderBaseException(f"Unknow provider state for the node={n.name}")
        return nodes_to_start, nodes_to_stop

