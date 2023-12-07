import logging
logger = logging.getLogger(__name__)

import asyncio
from typing import Optional

import grpc
import sys
sys.path.append("./protos")
from protos import externalgrpc_pb2
from protos import externalgrpc_pb2_grpc

from protos.externalgrpc_pb2 import NodeGroupDeleteNodesRequest, NodeGroupDeleteNodesResponse, NodeGroupsRequest, NodeGroupsResponse, RefreshRequest, RefreshResponse, NodeGroupForNodeRequest, NodeGroupForNodeResponse, GPULabelRequest,\
        GPULabelResponse, NodeGroupTargetSizeRequest, NodeGroupTargetSizeResponse, NodeGroupNodesRequest, NodeGroupNodesResponse, NodeGroupAutoscalingOptionsRequest, NodeGroupAutoscalingOptionsResponse, \
        NodeGroupDeleteNodesRequest, NodeGroupDeleteNodesResponse, GetAvailableGPUTypesRequest, GetAvailableGPUTypesResponse, NodeGroupIncreaseSizeRequest, NodeGroupIncreaseSizeResponse

from node import NodeGroup, Node, Status


class NodeGroupNotFound(Exception):
    pass

GPULabel = "k8s.magiccastle.com/gpu"

class CloudProvider(externalgrpc_pb2_grpc.CloudProviderServicer):

    def __init__(self):
        self.node_group = []

    async def GPULabel( self, request: GPULabelRequest, context: grpc.aio.ServicerContext,
                         ) -> GPULabelResponse:
        # TODO: handle GPU

        return GPULabelResponse(label=GPULabel)

    async def GetAvailableGPUTypes(self, request: GetAvailableGPUTypesRequest, context: grpc.aio.ServicerContext,
                         ) -> GetAvailableGPUTypesResponse:
        return GetAvailableGPUTypesResponse()


    async def NodeGroups( self, request: NodeGroupsRequest, context: grpc.aio.ServicerContext,
                         ) -> NodeGroupsResponse:

        return NodeGroupsResponse(nodeGroups=[ng.to_protobuf() for ng in self.node_group])

    async def NodeGroupForNode( self, request: NodeGroupForNodeRequest, context: grpc.aio.ServicerContext,
                         ) -> NodeGroupForNodeResponse:
        name = request.node.name
        for ng in self.node_group:
            for n in ng.nodes:
                if n.name == name:
                    return NodeGroupForNodeResponse(nodeGroup=ng.to_protobuf())

        return NodeGroupForNodeResponse(nodeGroup=NodeGroup().to_protobuf())

    async def Refresh( self, request: RefreshRequest, context: grpc.aio.ServicerContext,
                      ) -> RefreshResponse:
        logger.debug("Refresh")
        if len(self.node_group) == 0:
            nodes = [
                Node(name="minikube", status=Status.Running),
                Node(name="minikube-m02", status=Status.Running),
            ]
            self.node_group.append(NodeGroup(nodes, id="NodeGroupId"))

        return RefreshResponse()

    def get_node_group_by_id(self, id) -> NodeGroup:
        for ng in self.node_group:
            if ng.id == id:
                return ng

        raise NodeGroupNotFound("NodeGroup not found from request args")

    async def NodeGroupTargetSize( self, request: NodeGroupTargetSizeRequest, context: grpc.aio.ServicerContext,
                      ) -> NodeGroupTargetSizeResponse:
        ng = self.get_node_group_by_id(request.id)
        target_size = ng.target_size()

        return NodeGroupTargetSizeResponse(targetSize=target_size)

    async def NodeGroupNodes( self, request: NodeGroupNodesRequest, context: grpc.aio.ServicerContext,
                      ) -> NodeGroupNodesResponse:
        ng = self.get_node_group_by_id(request.id)

        return NodeGroupNodesResponse(instances=[n.to_protobuf() for n in ng.nodes])

    async def NodeGroupGetOptions( self, request: NodeGroupAutoscalingOptionsRequest, context: grpc.aio.ServicerContext,
                      ) -> NodeGroupAutoscalingOptionsResponse:

        options = request.defaults
        options.scaleDownUnneededTime.duration = 1

        return NodeGroupAutoscalingOptionsResponse(nodeGroupAutoscalingOptions=options)

    async def NodeGroupDeleteNodes( self, request: NodeGroupDeleteNodesRequest, context: grpc.aio.ServicerContext,
                      ) -> NodeGroupDeleteNodesResponse:
        logger.debug("DeleteNodes")
        ng = self.get_node_group_by_id(request.id)
        nodes_name = [n.name for n in request.nodes]

        ng.delete_nodes(nodes_name)

        return NodeGroupDeleteNodesResponse()

    async def NodeGroupIncreaseSize( self, request: NodeGroupIncreaseSizeRequest, context: grpc.aio.ServicerContext,
                      ) -> NodeGroupIncreaseSizeResponse:

        logger.debug("IncreaseSize")
        ng = self.get_node_group_by_id(request.id)

        ng.increase_size(request.delta)

        return NodeGroupIncreaseSizeResponse()


async def serve() -> None:
    server = grpc.aio.server()
    externalgrpc_pb2_grpc.add_CloudProviderServicer_to_server(CloudProvider(), server)
    listen_addr = "[::]:8086"
    server.add_insecure_port(listen_addr)
    logging.info("Starting server on %s", listen_addr)
    await server.start()
    await server.wait_for_termination()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(serve())
