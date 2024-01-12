
from requests.exceptions import Timeout
from enum import StrEnum
import logging

from node import Node, NodeStatus
logger = logging.getLogger(__name__)

from typing import List, Tuple
from providers.base import ProviderBase, ProviderBaseException, ProviderStatus
from config import Config

from providers.tfe_lib import TFECLient

class TFEProviderException(ProviderBaseException):
    """Raised when something bad happened in autoscale main"""

class TFEProvider(ProviderBase):
    POOL_VAR = "pool"

    def __init__(self, managed_nodes: List[Node], config: Config.TFE):
        super().__init__(managed_nodes)
        self.client = TFECLient(config.token, config.workspace)
        self.var_id, _ = self._fetch_pool()

    def get_nodes_status(self) -> dict[str, ProviderStatus]:
        nodes = {n.name: ProviderStatus.SHUTDOWN for n in self.managed_nodes}

        _, running_nodes = self._fetch_pool()
        for name in running_nodes:
            if name in nodes.keys():
                nodes[name] = ProviderStatus.RUNNING
        return nodes

    def _fetch_pool(self) -> Tuple[str, set[str]]:
        """Retrieve id and content of POOL variable from Terraform cloud
        """
        try:
            tfe_var = self.client.fetch_variable(self.POOL_VAR)
        except Timeout as exc:
            raise TFEProviderException("Connection to Terraform cloud timeout (5s)") from exc

        if tfe_var is None:
            raise TFEProviderException(
                f'"{self.POOL_VAR}" variable not found in TFE workspace "{self.client.workspace}"'
            )

        # When the pool variable was incorrectly initialized in the workspace,
        # we avoid a catastrophe by setting the initial pool as an empty set.
        if isinstance(tfe_var["value"], list):
            return tfe_var["id"], set(tfe_var["value"])
        return tfe_var["id"], set()

    def sync_status(self) -> dict[str, ProviderStatus]:
        nodes_status = self.get_nodes_status()
        nodes_to_start, nodes_to_stop = self._get_changes(nodes_status)

        if len(nodes_to_start) > 0 or len(nodes_to_stop) > 0:
            new_pool = set()
            for name, status in nodes_status.items():
                if status == ProviderStatus.RUNNING:
                    new_pool.add(name)
            new_pool |= set([n.name for n in nodes_to_start])
            new_pool -= set([n.name for n in nodes_to_stop])
            logger.debug(f"Changes to apply: {new_pool=}")

            try:
                self.client.update_variable(self.var_id, list(new_pool))
            except Timeout as exc:
                raise TFEProviderException(
                    "Connection to Terraform cloud timeout (5s)"
                ) from exc

            try:
                self.client.apply(f"K8S autoscaller apply {new_pool=}".strip())
            except Timeout as exc:
                raise TFEProviderException("Connection to Terraform cloud timeout (5s)") from exc

            logging.info(f"Autoscaller {new_pool=}")

        else:
            logger.debug(f"No changes to apply")
        return nodes_status
