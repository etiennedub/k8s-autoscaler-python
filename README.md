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

kubectl create cm externalgrpc-autoscaler-cluster-config --from-file=config.yaml --namespace=kube-system -o yaml
