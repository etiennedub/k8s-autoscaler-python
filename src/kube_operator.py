import logging

from providers.base import ProviderStatus
logger = logging.getLogger(__name__)

from typing import List
from kubernetes import client, config, watch
from kubernetes.client.models import v1_node_condition
from kubernetes.client.exceptions import ApiException
from kubernetes.config.config_exception import ConfigException
from node import Node, NodeStatus

from enum import StrEnum, auto


class KubeOperatorException(Exception):
    """Raised when something bad happened in KubeOperator"""

class OperatorStatus(StrEnum):
    # Match value with k8s api
    READY = 'True' # Node running
    DISCONNECTED = 'Unknown' # Node disconnected (network issue or node shutdown)
    DELETED = auto() # Node not present in the cluster

class KubeOperator:
    READY_TYPE = 'Ready'

    def __init__(self, managed_nodes: List[Node]):
        self.managed_nodes = managed_nodes
        try:
            # Try config file from env variable
            config.load_kube_config()
        except ConfigException:
            # Otherwise, load from cluster (running as pod)
            config.load_incluster_config()
        self.api = client.CoreV1Api()

    @staticmethod
    def _get_status_from_node_codition(conditions : list[v1_node_condition.V1NodeCondition]) -> OperatorStatus:
        status = OperatorStatus.DELETED
        for condition in conditions:
            if condition.type == KubeOperator.READY_TYPE:
                match condition.status:
                    case OperatorStatus.READY.value:
                        status = OperatorStatus.READY
                    case OperatorStatus.DISCONNECTED.value:
                        status = OperatorStatus.DISCONNECTED
                    case _:
                        raise KubeOperatorException(f"Unknown node status: {condition.status}")
                break
        return status

    def _get_status(self) -> dict[str, OperatorStatus]:
        nodes = {n.name: OperatorStatus.DELETED for n in self.managed_nodes}

        for n in self.api.list_node().items:
            name = n.metadata.name
            if name in nodes.keys():
                status = self._get_status_from_node_codition(n.status.conditions)
                nodes[name] = status
        return nodes

    def _delete_node(self, node):
        self.api.delete_node(node.name)

    def sync_status(self, nodes_provider_status: dict[str, ProviderStatus]):
        nodes_operator_status = self._get_status()
        for n in self.managed_nodes:
            match nodes_provider_status.get(n.name), nodes_operator_status.get(n.name):
                case [ProviderStatus.RUNNING, OperatorStatus.READY]:
                    n.status = NodeStatus.RUNNING
                case [ProviderStatus.RUNNING, OperatorStatus.DISCONNECTED]:
                    logger.warning(f"node={n.name} is in an UNKNOW state")
                    n.status = NodeStatus.UNKNOWN
                case [ProviderStatus.RUNNING, OperatorStatus.DELETED]:
                    # TODO: Handle the case where the node is manually deleted by the user independently of the autoscaler
                    n.status = NodeStatus.CREATING
                case [ProviderStatus.SHUTDOWN, OperatorStatus.READY]:
                    n.status = NodeStatus.DELETING
                case [ProviderStatus.SHUTDOWN, OperatorStatus.DISCONNECTED]:
                    self._delete_node(n)
                    n.status = NodeStatus.DELETING
                case [ProviderStatus.SHUTDOWN, OperatorStatus.DELETED]:
                    n.status = NodeStatus.SHUTDOWN
                case _:
                    raise KubeOperatorException(f"Unsupported status")

            # TODO: It would be favorable to use an independant kubelet config file on each node to set a unique provider id
            if n.status == NodeStatus.RUNNING:
                try:
                    node_api = self.api.read_node(n.name)
                    if node_api.spec.provider_id is None:
                        node_api.spec.provider_id = n.get_id()
                        self.api.patch_node(n.name, node_api)
                        logger.info(f"Set provider_id={n.get_id()} to node={n.name}")

                    if node_api.spec.provider_id != n.get_id():
                        raise KubeOperatorException("Node ProviderID is already set to an invalid value. " \
                                "Did you change the provider type on the same cluster? Otherwise, verify that `provider-id` is not set in Kubelet config. " \
                                f"Expected={n.get_id()} Value={node_api.spec.provider}")
                except ApiException as e:
                    logger.warning(f"Error reaching node={n.name}: {e}")
                    pass

