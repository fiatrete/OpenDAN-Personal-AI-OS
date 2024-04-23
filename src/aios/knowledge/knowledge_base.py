from abc import ABC, abstractmethod
import json
import os
import uuid
from typing import List

from ..proto.ai_function import ParameterDefine, SimpleAIAction, SimpleAIFunction
from ..agent.llm_context import GlobaToolsLibrary
from ..storage.objfs import ObjFS

import logging

logger = logging.getLogger(__name__)

class BaseKnowledgeGraph(ABC):
    _all_knowledge_bases = {}
    _default_kb = None
    @classmethod
    def get_kb(cls, kb_id:str):
        if kb_id is None:
            return cls._default_kb
        
        return cls._all_knowledge_bases.get(kb_id)

    @classmethod
    def add_kb(cls,kb:'BaseKnowledgeGraph',is_default=False):
        cls._all_knowledge_bases[kb.kb_id] = kb
        if is_default:
            cls._default_kb = kb

    @classmethod
    def remove_kb(cls,kb_id:str):
        if cls._default_kb is not None and cls._default_kb.kb_id == kb_id:
            cls._default_kb = None

        if cls._all_knowledge_bases.get(kb_id) is not None:
            del cls._all_knowledge_bases[kb_id]

    def __init__(self, kb_id: str,kb_desc:str=None):
        self.kb_id = kb_id
        if kb_desc is None:
            self.kb_desc = """
            """
        else:
            self.kb_desc = kb_desc

    def get_description(self)->str:
        return self.kb_desc

    # 读接口： 查询，浏览
    @abstractmethod
    async def serach(self,  query: str,query_type:str):
        pass

    @abstractmethod
    async def get_obj_by_path(self,path)->str:
        pass

    @abstractmethod
    async def get_obj_by_id(self,obj_id)->str:
        pass

    @abstractmethod
    async def list_by_path(self,base_path)->List[str]:
        pass
    
    @abstractmethod
    def list_source(self) -> List[str]:
        pass


    @abstractmethod
    async def add_obj(self,obj_id,obj_name,obj_content,paths) -> bool:
        pass

    @abstractmethod
    async def remove(self,remove_path) -> bool:
        pass

    @abstractmethod
    async def remove_obj(self,objid):
        pass

    @abstractmethod
    async def link(self,obj_id,paths) -> bool:
        pass

    @abstractmethod
    async def unlink(self,paths) -> bool:
        pass

    @abstractmethod
    async def update_obj(self,obj_id,new_content) -> bool:
        pass

    @staticmethod  
    def get_kb_default_desc_str():
        return """The basic design of the Knowledge Graph is
1. Each object can be described in JSON, and have a unique obj_id.
2. The object can be accessed through the PATH, and multiple paths can point to the same object.
3. Carefully understand the semantics of the path, and follow the description of the knowledge graph.You can list all the sub-paths of a path through the LIST operation
All Knowledge Graph APIs return are json format string."""


    # 写接口：通常由KnowledgePipeline调用
    @staticmethod
    def register_ai_functions():

        async def knowledge_graph_access(parameters):
            kb_id = parameters['kb_id']
            op_name = parameters['op']
            param = parameters['param']
            
            
            if op_name is None:
                logger.error("Operation type is not specified")
                return "Operation type is not specified"
            if param is None:
                logger.error("Operation parameters is not specified")
                return "Error! Operation parameters is not specified"
            param = json.loads(param)
            
            kb = BaseKnowledgeGraph.get_kb(kb_id)
            if kb is None:
                logger.error(f"Knowledge base is not found id:{kb_id}")
                return "Error! Knowledge base is not found"

            if op_name == "list":
                root_path = param.get("path")
                if root_path is None:
                    logger.error("Path is not specified")
                    return "Error! Path is not specified"
                
                return json.dumps(await kb.list_by_path(root_path), ensure_ascii=False)
            
            if op_name == "tree":
                root_path = param.get("path")
                if root_path is None:
                    logger.error("Path is not specified")
                    return "Error! Path is not specified"
                
                depth = param.get("depth")
                if depth is None:
                    depth = 3
                return json.dumps(await kb.tree(root_path,depth), ensure_ascii=False)
            
            if op_name == "read":
                obj_path = param.get("path")
                if obj_path is None:
                    logger.error("Path is not specified")
                    return "Error! Path is not specified"
                return json.dumps(await kb.get_obj_by_path(obj_path), ensure_ascii=False)
            
            if op_name == "get_obj":
                obj_id = param.get("obj_id")
                if obj_id is None:
                    logger.error("Object ID is not specified")
                    return "Error! Object ID is not specified"
                return json.dumps(await kb.get_obj_by_id(obj_id), ensure_ascii=False)
            
               
            return "Error! Operation type is not supported"
        
        # search is not supported currently
        func_desc = "Read knowledge graph, op_param format is as follows: list:{'path':$path}, read:{'path':$path}, get_obj:{'obj_id':$obj_id}, tree:{'path':$path,'depth':$depth}"
        parameters = ParameterDefine.create_parameters({
            "kb_id": "Knowledge Base ID",
            "op": "Operation Type,could be [list, read, get_obj]",
            "op_param": "Operation Param, must be a json string"
        })

        knowledge_graph_access_func = SimpleAIFunction("knowledge_base.knowledge_graph_read",
                                                        func_desc,
                                                        knowledge_graph_access,
                                                        parameters)
        GlobaToolsLibrary.get_instance().register_tool_function(knowledge_graph_access_func)

        async def knwoledge_graph_update(parameters):
            kb_id = parameters['kb_id']
            op_name = parameters['op']
            param = parameters['param']
            result = {}
            if op_name is None:
                logger.error("Operation type is not specified")
                result["result"] = "Error! Operation type is not specified"
                return json.dumps(result, ensure_ascii=False)
            if param is None:
                logger.error("Operation parameters is not specified")
                result["result"] = "Error! Operation parameters is not specified"
                return json.dumps(result, ensure_ascii=False)
            param = json.loads(param)
            
            kb = BaseKnowledgeGraph.get_kb(kb_id)
            if kb is None:
                logger.error(f"Knowledge base is not found id:{kb_id}")
                result["result"] = "Error! Knowledge base is not found"
                return json.dumps(result, ensure_ascii=False)
            
            if op_name == "write":
                write_path = param.get("path")
                if write_path is None:
                    logger.error("Path is not specified")
                    result["result"] = "Error! Path is not specified"
                    return json.dumps(result, ensure_ascii=False)
                obj_content = param.get("obj_json")
                if obj_content is None:
                    logger.error("Object content is not specified")
                    result["result"] = "Error! Object content is not specified"
                    return json.dumps(result, ensure_ascii=False)
                
                objid = uuid.uuid4()
                objname = os.path.basename(write_path)
                paths = []
                paths.append(write_path)
                if await kb.add_obj(objid,objname,obj_content['content'],paths):
                    result["result"] = "OK"
                    result['obj_id'] = objid
                else:
                    result["result"] = "Error! Add object failed"
                
            if op_name == "remove":
                remove_path = param.get("path")
                if remove_path is None:
                    logger.error("Path is not specified")
                    result["result"] = "Error! Path is not specified"
                    return json.dumps(result, ensure_ascii=False)
                
                if await kb.remove(remove_path):
                    result["result"] = "OK"
                else:
                    result["result"] = "Error! Remove path failed"

            if op_name == "remove_obj":
                obj_id = param.get("obj_id")
                if obj_id is None:
                    logger.error("Object ID is not specified")
                    result["result"] =  "Error! Object ID is not specified"
                    return result
                
                obj = await kb.get_obj_by_id(obj_id)
                if obj is None:
                    logger.error(f"Object is not found id:{obj_id}")
                    result["result"] = "Error! Object is not found"
                    return result
                
                await kb.remove_obj(obj_id)
                result["result"] = "OK" 

            if op_name == "set_obj":
                obj_id = param.get("obj_id")
                if obj_id is None:
                    logger.error("Object ID is not specified")
                    result["result"] = "Error! Object ID is not specified"
                    return json.dumps(result, ensure_ascii=False)
                
                obj = await kb.get_obj_by_id(obj_id)
                if obj is None:
                    logger.error(f"Object is not found id:{obj_id}")
                    result["result"] = "Error! Object is not found"
                    return result
                
                obj_content = param.get("obj_json")
                if obj_content is None:
                    logger.error("new object is not specified")
                    result["result"] = "Error! new object is not specified"
                    return json.dumps(result, ensure_ascii=False)
                
                await kb.update_obj(obj_id,obj_content)
                result["result"] = "OK"

            if op_name == "link":
                path_from = param.get("path")
                path_to = param.get("target") 
                if path_from is None or path_to is None:
                    logger.error("Path is not specified")
                    result["result"] = "Error! Path is not specified"
                    return json.dumps(result, ensure_ascii=False)

                objid = await kb.get_obj_by_path(path_to)
                if objid is None:
                    logger.error(f"Object is not found path:{path_to}")
                    result["result"] = "Error!Target Object is not found"
                    return json.dumps(result, ensure_ascii=False)
                
                await kb.link(objid,[path_from])
                result["result"] = "OK"
                
            if op_name == "unlink":
                path_will_remove = param.get("path")
                if path_will_remove is None:
                    logger.error("Path is not specified")
                    result["result"] = "Error! Path is not specified"
                    return json.dumps(result, ensure_ascii=False)

                await kb.unlink([path_will_remove])
                result["result"] = "OK"

            return json.dumps(result, ensure_ascii=False)
        

        OperationParames = """Parameters is a json string, the format is as follows:
        write:{'path':$path,'obj_json':$obj_json},
        remove:{'path':$path},
        remove_obj:{'obj_id':$obj_id},
        set_obj:{'obj_id':$obj_id,'obj_json':$new_obj_json},
        link:{'path':$path,'target':$target_obj_path},
        unlink:{'path':$path}
"""
        parameters = ParameterDefine.create_parameters({
            "kb_id": "Knowledge Base ID",
            "op": "Operation Type,could be [write, remove, remove_obj, set_obj, link, unlink",
            "param": OperationParames
        })

        knowledge_graph_update_func = SimpleAIFunction("knowledge_base.knowledge_graph_update",
                                                        "Update Knowledge Graph APIs",
                                                        knwoledge_graph_update,
                                                        parameters)
        GlobaToolsLibrary.get_instance().register_tool_function(knowledge_graph_update_func)


class ObjFSKnowledgeGrpah(BaseKnowledgeGraph):
    def __init__(self, kb_id:str,db_path:str,kb_desc:str=None):
        super().__init__(kb_id,kb_desc)
        self.db_path = db_path
        self.obj_storage : ObjFS = ObjFS(db_path)
    
    async def serach(self,  query: str,query_type:str):
        pass

    def list_source(self):
        pass

    async def get_obj_by_path(self,path)->str:
        return self.obj_storage.get_obj_by_path(path)
    
    async def get_obj_by_id(self,obj_id)->str:
        return self.obj_storage.get_obj_by_id(obj_id)
    
    async def list_by_path(self,base_path)->List[str]:
        return self.obj_storage.list_paths(base_path)
    
    async def tree(self,base_path,depth:int)->str:
        return self.obj_storage.tree(base_path,depth)
    
    async def add_obj(self,obj_id,obj_name,obj_content,paths)->bool:
        self.obj_storage.add_obj(obj_id,obj_name,obj_content,paths)

    #todo 更新默认是做dict的merge
    async def update_obj(self, obj_id, new_content)->bool:
        return self.obj_storage.update_obj(obj_id,new_content)
    
    async def remove(self,remove_path)->bool:
        self.obj_storage.remove_path(remove_path)

    async def remove_obj(self,objid)->bool:
        self.obj_storage.remove_obj(objid)

    async def link(self,from_path,target_path)->bool:
        objid = self.obj_storage.get_obj_by_path(target_path)
        if objid is None:
            return False
        self.obj_storage.add_path(objid,from_path)
        return True

    async def unlink(self,paths)->bool:
        self.obj_storage.remove_path(paths)

    


