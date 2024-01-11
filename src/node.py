import logging
logger = logging.getLogger(__name__)

from protos.k8s.io.apimachinery.pkg.api.resource.generated_pb2 import Quantity

from typing import Optional

from dataclasses import dataclass
from enum import StrEnum, auto

from protos.externalgrpc_pb2 import NodeGroup as NodeGroupProtobuf
from protos.externalgrpc_pb2 import Instance as InstaceProtobuf
from protos.externalgrpc_pb2 import InstanceStatus
from protos.k8s.io.api.core.v1.generated_pb2 import NodeStatus as K8SNodeStatus

class NodeStatus(StrEnum):
    RUNNING = auto()
    CREATING = auto()
    SHUTDOWN = auto()
    DELETING = auto()
    UNKNOWN = auto()

class ActionFlag(StrEnum):
    TO_DELETE = auto()
    TO_START = auto()

@dataclass
class Specs:
    cpus: int
    gpus: int
    ram: float

    def to_protobuf(self) -> K8SNodeStatus:
        # Mapping define in k8s.io/api/core/v1/types.go
        capacity = {
                "cpu": Quantity(string=str(self.cpus)),
                "memory": Quantity(string=f"{self.ram}Mi"),
                "pods": Quantity(string="100"), # TODO: Set real value
                "ephemeral-storage": Quantity(string="10Gi"), # TODO real value for storage
                "nvidia.com/gpu": Quantity(string=f"{self.gpus}")
            }
        return K8SNodeStatus(capacity=capacity, allocatable=capacity)


@dataclass
class Node:
    name: str
    status: NodeStatus
    provider_id: str
    flag: Optional[ActionFlag] = None

    def get_id(self) -> str:
        return f"{self.provider_id}://{self.name}"

    def to_protobuf(self) -> InstaceProtobuf:
        match self.status:
            case NodeStatus.CREATING:
                status = InstanceStatus.instanceCreating
            case NodeStatus.RUNNING:
                status = InstanceStatus.instanceRunning
            case NodeStatus.DELETING:
                status = InstanceStatus.instanceDeleting
            case NodeStatus.UNKNOWN:
                logger.warning(f"Node={self.name} in UNKNOW state")
                status = InstanceStatus.unspecified
            case NodeStatus.SHUTDOWN:
                raise Exception("SHUTDOWN node should not be exposed on the API")
            case _:
                raise Exception("Invalid node state")

        return InstaceProtobuf(id=self.get_id(), status=InstanceStatus(instanceState=status))


class NodeGroup:
    MIN_SIZE = 0

    def __init__(self, nodes=[], id='', specs: Specs = Specs(0, 0, 0)):
        self.nodes = nodes
        self.id = id
        self.specs = specs

    def max_size(self) -> int:
        return len(self.nodes)

    def min_size(self) -> int:
        return self.MIN_SIZE

    def target_size(self) -> int:
        return len(self.get_running_nodes())

    def debug(self) -> str:
        return f"{self.id=}, {self.min_size()=}, {self.max_size()=}, {self.target_size()=}"

    def _start_available_node(self):
        for n in self.nodes:
            if n.status in [NodeStatus.SHUTDOWN, NodeStatus.DELETING] and n.flag is None:
                n.flag = ActionFlag.TO_START
                return n

    def increase_size(self, delta):
        nodes = []
        for _ in range(delta):
            node = self._start_available_node()
            if node is None:
                raise Exception("No node available")
            else:
                nodes.append(node)

        logger.debug(f"TO_START: {delta=} {nodes}")


    def get_running_nodes(self, include_deleting=False):
        nodes = []
        flags = [NodeStatus.RUNNING, NodeStatus.CREATING]
        if include_deleting:
            flags.append(NodeStatus.DELETING)

        for n in self.nodes:
            if n.status in flags:
                nodes.append(n)
        return nodes


    def delete_nodes(self, nodes_name):
        nodes = self._get_nodes_by_name(nodes_name)
        for n in nodes:
            n.flag = ActionFlag.TO_DELETE
        logger.debug(f"TO_DELETE: {nodes}")

    def _get_nodes_by_name(self, names):
        nodes = []
        for n in self.nodes:
            if n.name in names:
                nodes.append(n)
        return nodes

    def to_protobuf(self):
        return NodeGroupProtobuf(id=self.id, minSize=self.min_size(), maxSize=self.max_size(), debug=self.debug())


