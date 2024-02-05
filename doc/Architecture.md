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
