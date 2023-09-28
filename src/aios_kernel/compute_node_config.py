"""
Configuration for nodes:

```
├── nodes
│ └── llama
|   └── 0
|   |   └── url
|   |   └── model_name
|   └── 1
|       └── url
|       └── model_name
```
"""
import logging
from typing import List

import os
import toml

from .local_llama_compute_node import LocalLlama_ComputeNode
from .storage import AIStorage

# define singleton class knowledge pipline
class ComputeNodeConfig:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = ComputeNodeConfig()
            cls._instance.__singleton_init__()

        return cls._instance
    
    def initial(self) -> List[LocalLlama_ComputeNode]:
        config_path = self.__config_path()
        logging.info(f"initial nodes from {config_path}")

        if os.path.exists(config_path):
            self.config = toml.load(self.__config_path())
            if self.config is None:
                return []
            
            nodes = []
            llama_nodes_cfg = self.config["llama"]
            if llama_nodes_cfg is not None:
                for cfg in llama_nodes_cfg:
                    node = LocalLlama_ComputeNode(url=cfg["url"], model_name=cfg["model_name"])
                    nodes.append(node)

            return nodes

        return []
        
    def save(self):
        with open(self.__config_path(), "w") as f:
            toml.dump(self.config, f)
        
    def add_node(self, model_type: str, url: str, model_name: str):
        if model_type == "llama":
            llama_nodes_cfg = self.config.get("llama") or []
            for cfg in llama_nodes_cfg:
                if url == cfg["url"] and model_name == cfg["model_name"]:
                    return
            llama_nodes_cfg.append({"url": url, "model_name": model_name})
            self.config["llama"] = llama_nodes_cfg
    
    
    def remove_node(self, model_type: str, url: str, model_name: str):
        if model_type == "llama":
            llama_nodes_cfg = self.config.get("llama") or []
            for i in range(0, len(llama_nodes_cfg)):
                cfg = llama_nodes_cfg[i]
                if url == cfg["url"] and model_name == cfg["model_name"]:
                    llama_nodes_cfg.pop(i)

    def list(self) -> str:
        return toml.dumps(self.config)

    def __singleton_init__(self):
        self.config = {}

    @classmethod
    def __config_path(cls) -> str:
        user_data_dir = AIStorage.get_instance().get_myai_dir()
        return os.path.abspath(f"{user_data_dir}/etc/compute_nodes.cfg.toml")
