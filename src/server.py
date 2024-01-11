import logging
import pathlib
import argparse
import sys
import os

# Add protos in python path
sys.path.append(os.path.dirname(__file__) + "/protos")


from providers.tfe import TFEProvider


logger = logging.getLogger(__name__)

from providers.minikube import MinikubeProvider
import asyncio
from typing import Optional
import re

import yaml
import grpc
from protos import externalgrpc_pb2
from protos import externalgrpc_pb2_grpc

from protos.externalgrpc_pb2 import NodeGroupDeleteNodesRequest, NodeGroupDeleteNodesResponse, NodeGroupsRequest, NodeGroupsResponse, RefreshRequest, RefreshResponse, NodeGroupForNodeRequest, NodeGroupForNodeResponse, GPULabelRequest,\
        GPULabelResponse, NodeGroupTargetSizeRequest, NodeGroupTargetSizeResponse, NodeGroupNodesRequest, NodeGroupNodesResponse, NodeGroupAutoscalingOptionsRequest, NodeGroupAutoscalingOptionsResponse, \
        GetAvailableGPUTypesRequest, GetAvailableGPUTypesResponse, NodeGroupIncreaseSizeRequest, NodeGroupIncreaseSizeResponse, NodeGroupTemplateNodeInfoRequest,  NodeGroupTemplateNodeInfoResponse

from node import NodeGroup, Node, NodeStatus, Specs
from kube_operator import KubeOperator

from config import Config


class NodeGroupNotFound(Exception):
    pass

GPULabel = "k8s.magiccastle.com/gpu"

GROUP_ID_REGEX = re.compile(r'\D+(?=\d)') # TODO: Probably safer to set the group in the config file
POOL_TF_VARIABLE = "pool"

class CloudProvider(externalgrpc_pb2_grpc.CloudProviderServicer):
    def __init__(self, config_path="config.yaml"):
        self.node_group = []
        config = Config.from_yaml(config_path)

        for instance in config.instances:
            name = instance.name
            group_id = GROUP_ID_REGEX.match(name)
            if group_id:
                group_id = group_id.group(0)

                node = Node(name=name, status=NodeStatus.UNKNOWN, provider_id=config.provider.id)
                specs = Specs(**instance.specs)

                existing_node_group = False
                for node_group in self.node_group:
                    if node_group.id == group_id:
                        existing_node_group = True
                        assert node_group.specs == specs
                        node_group.nodes.append(node)

                if not existing_node_group:
                    node_group = NodeGroup(nodes=[node], id=group_id, specs=specs)
                    self.node_group.append(node_group)

        all_nodes = [n for ng in self.node_group for n in ng.nodes]
        match config.provider:
            case Config.Minikube():
                self.provider = MinikubeProvider(all_nodes)
            case Config.TFE():
                self.provider = TFEProvider(all_nodes, config.provider)
            case _:
                raise Exception("InvalidType for provider")
        logger.debug(f"Provider: {self.provider}")

        self.operator = KubeOperator(all_nodes)

        # Update initial state
        provider_nodes_state = self.provider.sync_status()
        self.operator.sync_status(provider_nodes_state)

    async def GPULabel( self, request: GPULabelRequest, context: grpc.aio.ServicerContext,
                         ) -> GPULabelResponse:
        # TODO: handle GPU

        return GPULabelResponse(label=GPULabel)

    async def GetAvailableGPUTypes(self, request: GetAvailableGPUTypesRequest, context: grpc.aio.ServicerContext,
                         ) -> GetAvailableGPUTypesResponse:
        return GetAvailableGPUTypesResponse()


    async def NodeGroups( self, request: NodeGroupsRequest, context: grpc.aio.ServicerContext,
                         ) -> NodeGroupsResponse:
        logger.debug(f"NodeGroups")

        return NodeGroupsResponse(nodeGroups=[ng.to_protobuf() for ng in self.node_group])

    async def NodeGroupForNode( self, request: NodeGroupForNodeRequest, context: grpc.aio.ServicerContext,
                         ) -> NodeGroupForNodeResponse:
        name = request.node.name
        for ng in self.node_group:
            for n in ng.nodes:
                if n.name == name:
                    logger.debug(f"NodeGroupForNode: node={name} found")
                    return NodeGroupForNodeResponse(nodeGroup=ng.to_protobuf())

        # Empty NodeGroup for unmanaged node
        logger.debug(f"NodeGroupForNode: node={name} not found")
        return NodeGroupForNodeResponse(nodeGroup=NodeGroup().to_protobuf())

    async def Refresh( self, request: RefreshRequest, context: grpc.aio.ServicerContext,
                      ) -> RefreshResponse:
        provider_nodes_state = self.provider.sync_status()
        self.operator.sync_status(provider_nodes_state)

        return RefreshResponse()

    def get_node_group_by_id(self, id) -> NodeGroup:
        for ng in self.node_group:
            if ng.id == id:
                return ng

        raise NodeGroupNotFound("NodeGroup not found from request args")

    async def NodeGroupTargetSize( self, request: NodeGroupTargetSizeRequest, context: grpc.aio.ServicerContext,
                      ) -> NodeGroupTargetSizeResponse:
        ng = self.get_node_group_by_id(request.id)
        logger.debug(f"NodeGroupTargetSize: {ng.id}")
        target_size = ng.target_size()

        return NodeGroupTargetSizeResponse(targetSize=target_size)

    async def NodeGroupNodes( self, request: NodeGroupNodesRequest, context: grpc.aio.ServicerContext,
                      ) -> NodeGroupNodesResponse:
        ng = self.get_node_group_by_id(request.id)
        logger.debug(f"NodeGroupNodes: {ng.id}")

        active_nodes = ng.get_running_nodes(include_deleting=True)
        return NodeGroupNodesResponse(instances=[n.to_protobuf() for n in active_nodes])

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

    async def NodeGroupTemplateNodeInfo( self, request: NodeGroupTemplateNodeInfoRequest, context: grpc.aio.ServicerContext,
                      ) -> NodeGroupTemplateNodeInfoResponse:
        ng = self.get_node_group_by_id(request.id)
        node_info = {
                "status" : ng.specs.to_protobuf()
                }
        return NodeGroupTemplateNodeInfoResponse(nodeInfo=node_info)



async def serve(config) -> None:
    server = grpc.aio.server()
    externalgrpc_pb2_grpc.add_CloudProviderServicer_to_server(CloudProvider(config_path=config), server)
    listen_addr = "[::]:8086"
    server.add_insecure_port(listen_addr)
    logging.info("Starting server on %s", listen_addr)
    await server.start()
    await server.wait_for_termination()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Autoscaler')
    parser.add_argument('config', type=pathlib.Path)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    asyncio.run(serve(args.config))
