## LLM / AI 相关框架
### LLM Process

LLM调用封装的最小单元，提供了一系列最基础的支持

流程上 inpurt, prepare promot, llm_function_call_loop, post_llm , llmresult parser, AI Action
功能上 动态类型系统 load_from_config,llm_process_loader

### Agent
从Agent的视角定义了Agent的LLM行为逻辑
Process behavior  (响应)
Task/Todo Loop (自主)
Self Loop (自省)


#### Agent.Memory
Memory模块设计的主要目的是能按一定的模式，在Token Limit的情况下构成Agent的一些上下文。
Memory的原始记录写入：原则上说，Agent的任何LLM行为都应至少将input/resp 写入Memory,毕竟LLM是非常高开销的行为。LLM的过程可以视情况写入（inner function的调用，action的执行，根据input构造的完整提示词等）
Memory的使用：LLM过程在构造提示词的“已知信息”部分时，通常都会有加载Memory的需求。尤其是在Input并不包含完整信息的情况下（非幂等LLM推理），更需要根据“上下文”来理解Input的含义。这在“ChatCompetition”过程中尤为明显。

使用Memory基本是两种方式
1. 加载写入的原始记录
2. 访问根据原始记录加工（Self-Thinking）后的Object-Summary。或则访问一个根据原始记录整理的，用文件系统方式组织的“记忆片段”

这里的核心痛点是：一个LLM过程，如何根据Input加载合适的Memory成为“已知信息”。
1. 如果明确的知道Input属于一个session，那么可以加载这个session相关的所有record(注意token limit和最大条数)与session的summary，其它的Memory的信息通过inner_function访问。但要防止LLM过程中对Inner function的过度使用
2. 在不明确的情况下，如何判断input属于哪个session?（包括是否需要创建新的session）

从上述思考中，得到现在的设计方案：
1. 依旧保留Session，且创建session是明确的用户行为。有一些tunnel根本没有创建session的能力。UI可以用 Lite-LLM来进行辅助的session合并（比如类似GMail的Email归集）。系统可以基于session做“已知信息”的自动加载
2. 在处理Input时，允许使用Agent.Memory的接口来访问更多的Memory的内容。从流程上看，这个过程和访问KB的原理是基本一致的。
3. Self-Thinking的过程中，既要对Session进行整理（得到Session Summary）,也要站在更全局的角度对涉及到的Object进行整理（得到Object Summary）。
4. Self-Thinking的过程也是以session为单位的,以更新session-summary为首要目标，并可以在Thiking的过程中，访问已有的object-summary，选择性的更新object-summary
5. Self-Thinking会尽量以时间从新到旧处理所有的原始记录，因此会涉及到对多个Session的Summary的更新。

设计方案的主要风险在于inner function模式可能会带来大量的，无用的object summary查询。

对于UI上不方便创建Session的情况：
1. 通过标题尝试自动创建
2. 通过时间尝试自动创建
3. 既然用户看到的就是一个session，那么我们就必须当一个session来处理


一些推论：
Agent通过一个DB list来访问/写入结构化数据，并拥有自己创建DB的能力
Agent通过一个FileSystem来访问/创建非结构化数据，并拥有理解文件系统组织设计的能力
“不要给Agent直接扩展能力，而是尽量给Agent扩展元能力（读说明书的能力）”

#### Agent.Workspace

#### Agent.behavior

### Workflow
一组Agent共享Work space后的流程
Task可以分配给不同的Agent
Todo的Do和Check可以分配给不同的Agent

## Knowledge Base （sisi)
AI First的未来文件系统

## Agent 能力扩展框架

### AI Function / Action 
最重要的扩展框架

### Environment
可以通过 {environment.xxx} 读取

### Code Interpreter  
Agent 能不能写代码是一个重要的理念之争
能写代码的Agent想象空间大，是通往AGI的必然之路，但不够稳定可预期
不能写代码的Agent可以专注于组合使用基础的能力，稳定可靠的

## AI系统组件
### AI Compute Kernel
通过AI Compute Kernel对 LLM, AIGC等新一代的AI基础能力进行抽象
通过Compute Node可以对这些基础能力进行不同的实现 

### AI Models
模型的fine-tune Pipeline
LoRA的Pipeline

### Contact Manage

基于Contact的自然语言权限控制

### Tunnel
可以使用开放API的通信软件，于自己的AI时刻保持沟通

### Spider
持续的导入用户在旧时代的数据。
从Web2->web3

### Calendar (Calendar是否应该是Agent.Worksapce的一部分）


### 基础的pkg_loader
支持一系列可安装的扩展
可扩展的扩展是AIOS的开发者需要重点关注的

Agent （用自然语言扩展）
Workflow （用自然语言扩展）
Plugin:(需要会写代码）
	AI Function / Action
	Environment
	Knowledge Pipeline
	LLM Process
	Compute Node

### System Config Manage

Zone Config-> System Config

## UI 

### Installer 
图形化的安装界面，帮助用户能快速的安装使用
我们也会在这里讨论面向用户的AIOS的过渡性安装逻辑

### WebUI & OS Desktop
系统控制面板
Agent/Workflow管理   
新Outlook
	会话管理 （于Agent会话）
	日程管理
	Todo管理

新Dropbox
	Knowledge Base浏览
	Knowledge Base查询
	
应用商店
	
### AIOS Shell

### Personal Station (新个人主页）
内容的发布/联系人内容的查看/个人日历的公开

## Frame Service （完全未开始）
通过Frame Service，让AIOS成为一个典型的网络系统（Personal Server OS）
这一块会复用很多CYFS/Bucky OS 的基础设计
这一层AI不会直接使用，这一层支持AI系统组件的实现
在用户看来，这一层的功能都是高级的，偏向系统维护的。很少会直接使用

### zone & node-daemon
NOS的booter

### Runtime (Container) Manage
这里抽象了系统的运行时模型
通过容器技术对可扩展组件的权限进行控制，保护系统的隐私安全

### d-Storage & Named Object
Named- Object File System
D-RDB
D-VDB

### BUS
系统消息总线，在不同的系统组件中路由消息

### CYFS (httpv4) Gateway
