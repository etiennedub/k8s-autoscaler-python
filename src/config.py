from dataclasses import dataclass
from typing import List
import yaml


@dataclass
class Config:
    @dataclass
    class TFE:
        token: str
        workspace: str
        id = "tfe"

    @dataclass
    class Minikube:
        id = "minikube"

    @dataclass
    class Instance:
        name: str
        specs: dict

    provider: TFE | Minikube
    instances: List[Instance]

    @staticmethod
    def from_yaml(yaml_path):
        with open(yaml_path, 'r') as f:
           config = yaml.safe_load(f)

        provider_config = config['provider']
        match list(provider_config.keys()):
            case [Config.Minikube.id]:
                provider = Config.Minikube()
            case [Config.TFE.id]:
                provider = Config.TFE(**provider_config['tfe'])
            case _:
                raise Exception("Invalid provider in config file")
        instances = []
        for instance in config['instances']:
            assert len(instance) == 1
            for name, param in instance.items():
                instances.append(Config.Instance(name=name, **param))

        return Config(provider=provider, instances=instances)
