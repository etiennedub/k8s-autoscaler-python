# K8S Autoscaler Python

## Usage
The autoscaler run from your Kubernetes cluster.

### Config
The configuration file define the provider used, with his correpoinding credentials, and the instances available for scalling. The instances don't need to be currently running be they must be avaiable for scalling.

Follow this example for the configuration file:
```
---
provider:
  tfe:
    token: <Terraform Cloud Token>
    workspace: <Terraform Cloud Workspace>
instances:
  - node1:
      specs:
        cpus: 2
        gpus: 0
        ram: 2048
  - node2:
      specs:
        cpus: 2
        gpus: 0
        ram: 2048
```

### Deployment
You must expose your config file as a ConfigMap (your config must be named `config.yaml` to match with the deployment chart):
```
kubectl create cm externalgrpc-autoscaler-cluster-config --from-file=config.yaml --namespace=kube-system -o yaml
```

Then apply the charts from the `deploy` folder:
```
kubectl apply -f cluster-autoscaler-config.yaml -f ./cluster-autoscaler.yaml -f ./externalgrpc-autoscaler-service.yaml -f ./externalgrpc-autoscaler.yaml
```

## Developement

### Run from source

### Protobuf generation

Protobuf:
`git clone https://github.com/kubernetes/kubernetes.git`

```
python -m grpc_tools.protoc \
  -I/home/etienned/Documents/CalculQubec/autoscaler/cluster-autoscaler/cloudprovider/externalgrpc/protos \
  -I/home/etienned/Documents/CalculQubec/kubernetes/staging/src \
  --python_out=. --pyi_out=. --grpc_python_out=. \
  /home/etienned/Documents/CalculQubec/autoscaler/cluster-autoscaler/cloudprovider/externalgrpc/protos/externalgrpc.proto \
  /home/etienned/Documents/CalculQubec/kubernetes/staging/src/k8s.io/api/core/v1/generated.proto
```

## TODOs

* Encrypt communication between Client/Server
* GPU Support



