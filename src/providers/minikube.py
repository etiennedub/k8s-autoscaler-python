from enum import StrEnum
import logging
logger = logging.getLogger(__name__)

from node import Node

from typing import List
import re
import json
from providers.base import ProviderBase, ProviderBaseException, ProviderStatus

class MinikubeOp(StrEnum):
    START = "start"
    STOP = "stop"

from subprocess import run, PIPE

class MinikubeProviderException(ProviderBaseException):
    """Raised when something bad happened in autoscale main"""

class MinikubeProvider(ProviderBase):

    def get_nodes_status(self) -> dict[str, ProviderStatus]:
        nodes = {n.name: ProviderStatus.SHUTDOWN for n in self.managed_nodes}

        minikube_output = run(["minikube", "status", "-o=json"],
                  stderr=PIPE, stdout=PIPE)
        node_status = json.loads(minikube_output.stdout.decode())

        for n in node_status:
            name = n['Name']
            state = n['Host']
            if name in nodes.keys() and state == 'Running':
                nodes[name] = ProviderStatus.RUNNING
        return nodes

    def _apply_op(self, nodes: list[Node], op: MinikubeOp):
        for n in nodes:
            run(["minikube", "node", op.value, n.name],
                      stderr=PIPE, stdout=PIPE)
            logger.info(f"    Minikube {op} {n}")
            n.flag = None

    def sync_status(self) -> dict[str, ProviderStatus]:
        nodes_status = self.get_nodes_status()
        nodes_to_start, nodes_to_stop = self._get_changes(nodes_status)

        if len(nodes_to_start) > 0 or len(nodes_to_stop) > 0:
            logger.info(f"Changes to apply:")
            self._apply_op(nodes_to_start, MinikubeOp.START)
            self._apply_op(nodes_to_stop, MinikubeOp.STOP)
        else:
            logger.debug(f"No changes to apply")

        return nodes_status
