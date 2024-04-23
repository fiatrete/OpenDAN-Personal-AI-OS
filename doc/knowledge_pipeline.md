# 配置knowledge pipeline
knowledge pipeline 扫描指定的输入，把输入的内容构建为结构化的knowledge object，之后依照使用knowledge的应用场景，为object创建各种各样的索引。
## Input
输入定义从个人数据来源转换成结构化的knowledge object的过程，并且定义在object上调用parser的粒度。比如典型的几种Input的实现：
+ 本地目录：指定本地目录，扫描本地目录的所有文件，并且监听他的更新；对每个一个文件生成object并且写入object store；对每一个新产生的object调用parser；
+ 个人邮箱：扫描个人邮箱收件箱，并且监听新的邮件；对每一封邮件生成email object并且写入object store；对每一个新产生的email object调用parser；
+ 浏览器上下文：实现浏览器插件，对当前浏览的页面元素通过rpc传入对应的input 后端实现，生成rich text object；对每一个新产生的rich text object调用parser；

## Parser
Parser定义从input 输入的object 创建索引的过程；包括但不限于以下主要手段，以及他们的组合：
+ 向量化之后写入vector store
+ 创建各种维度的RDB，NoSQL索引
+ 向Agent send object

配置Pipeline 应当包含以下几个部分：
+ Input method：包含实现input的 python module
+ Input params：inpu module的参数，比如本地路径，邮箱地址
+ Parser method：包含实现parser的 python module；如果Parser是指向Agent，这个配置是可以简化成Agent instance name；

# Knowledge pipeline manager
pipeline 管理会类似agent manager，manager管理pipeline config，从config 创建instance在后台持续运行， knowledge pipeline manager 也需要处理pipeline instance的状态管理.

集成到aios shell中，加入如下命令：
+ knowledge pipelines： 返回当前运行中的pipeline实例
+ knowledge journal $pipeline [$topn]： 查询当前pipeline运行的journal日志 
+ knowledge query $object_id: 查询指定knowledge object的内容

# 在aios shell中添加新的knowledge pipeline
在$home/myai/knowledge_pipelines/, 或者开发模式下在 $source_root/rootfs/knowledge_pipelines/ 目录中，添加新的pipeline 目录, 以下以内建的pipeline Mia为例说明：

## pipeline.toml
创建pipeline.toml配置文件
+ name字段指定全局唯一的pipeline name
+ input.module字段指向相对pipeline目录的input实现
+ input.params字段定义input的输入参数，不同的input实现可以有不同的参数格式
+ parser 部分也是类似
``` toml
name = "Mia"
input.module = "input.py"
input.params.path = "${myai_dir}/data"
parser.module = "parser.py"
parser.params.path = "${myai_dir}/knowledge/indices/embedding"
```

## input
input模块至少应当实现：
```python
async def next(self):
```
定义input class，实现异步迭代生成器方法next，扫描输入，对其中的每一个元素生成结构化的knowledge object；
+ 如果input中的所有元素都扫描完成了，返回None, pipeline会被标记为finish
+ 如果input可pending，等待新的输入，返回（None, None）
+ 如果要把创建的object传递到parser，返回（object_id, journal_str）,其中journal_str是产生的journal 日志中的input 部分；
Mia中的实现就是扫描目录中的文件，对文本和图片创建object；
```python
def init(env: KnowledgePipelineEnvironment, params: dict)
```
创建input class的实例并返回

## parser
parser模块至少应当实现
```python
async def parse(self, object: ObjectID) -> str:
```
定义parser class，实现parse成员方法,对input中返回的object_id创建索引，返回journal_str.
Mia中的实现就是对输入的object内容embedding，并且保存到chromadb中；
```python
def init(env: KnowledgePipelineEnvironment, params: dict)
```
创建parser class的实例并返回

# 使用pipeline创建的索引
pipeline定义了创建knowledge object 和索引的过程，对应的要使用pipeline创建的索引完成工作。
还是以内建的Mia为例，不止创建名为Mia的pipeline，还在Agent中加入了查询Mia pipeline创建出来的chromadb的 Agent Mia；
## query.py
query 模块并不是pipeline的一部分，其逻辑是跟parser是一致的，在query中定义了一个agent可访问的query function，输入prompt，返回chromadb中embedding相近的object id；

## agent.toml
```toml
owner_env = "../../knowledge_pipelines/Mia/query.py"
```
在Mia的agent template配置里，引用query模块创建的query function；并且编辑好让Mia推理调用query方法的提示词。





