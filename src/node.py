import logging
from dataclasses import dataclass
from enum import StrEnum, auto

from protos.externalgrpc_pb2 import NodeGroup as NodeGroupProtobuf
from protos.externalgrpc_pb2 import Instance as InstaceProtobuf
from protos.externalgrpc_pb2 import InstanceStatus

class Status(StrEnum):
    Running = auto()
    Starting = auto()
    Deleting = auto()

@dataclass
class Node:
    name: str
    status: Status

    def to_protobuf(self) -> InstaceProtobuf:
        match self.status:
            case Status.Running:
                status = InstanceStatus.instanceRunning
            case Status.Starting:
                status = InstanceStatus.instanceCreating
            case Status.Deleting:
                status = InstanceStatus.instanceDeleting

        return InstaceProtobuf(id=self.name, status=InstanceStatus(instanceState=status))


class NodeGroup:
    MIN_SIZE = 0

    def __init__(self, nodes=[], id=''):
        self.nodes = nodes
        self.id = id

    def max_size(self) -> int:
        return len(self.nodes)

    def min_size(self) -> int:
        return self.MIN_SIZE

    def target_size(self) -> int:
        count = 0
        for n in self.nodes:
            if n.status in [Status.Running, Status.Starting]:
                count += 1
        return count

    def debug(self) -> str:
        return ""

    def increase_size(self, delta):
        for _ in range(delta):
            name = f"minikube-{len(self.nodes)+1}"
            self.nodes.append(Node(name=name, status=Status.Starting))
            print(f"Starting {name}....")

    def delete_nodes(self, nodes_name):
        nodes = self._get_nodes_by_name(nodes_name)
        for n in nodes:
            n.status = Status.Deleting
            print(f"Deleting {n.name}....")

    def _get_nodes_by_name(self, names):
        nodes = []
        for n in self.nodes:
            if n.name in names:
                nodes.append(n)
        return nodes

    def to_protobuf(self):
        return NodeGroupProtobuf(id=self.id, minSize=self.min_size(), maxSize=self.max_size(), debug=self.debug())


