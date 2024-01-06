# AI Function list (Local)

根据新的Function/Action 定义，我们需要记录系统目前提供的所有注册到GlobaToolsLibrary里的function,方便配置组合
功能扩展只需要扩展function就好了，Action可以通过Function直接得到。

本文档提到的AI Function一般都是Local Function, 基于这个架构，我们可以用Web3的思路整合AI Service。

## Context Prepare
很多AIFUnction的正确调用都需要在参数里提供一个状态上下文。这个上下文的准备一般由LLProcess完成.而可以通过提示词实时改变的参数是AIFunction的真参数。目前需要做Context Prepare的主要和Agent相关的基础函数。


## Agent Core

Agent Core中提供的，与Agent/Workflow 状态关联的基础函数，是Agent的核心设计。对Agent来说，这些基础能力通常都是打开的，我们需要非常谨慎的思考哪些功能应该放到Agent Core中。

根据我们的架构设计，Agent Core的函数包含 Agent的Memory + TODO能力（Plan）。通过这些基础函数，支持了Agent的

- Process Message
- Planing: 让Agent可以基于Zone的权限Process Task/Todo
- Self-Think: Process的经验进行总结
- Self-Improve: 对Agent的提示词进行持续的自我改进。


### logs

logs通常代表Agent的短期记忆，目前有两种Log:chatlog和worklog
目前我们并不鼓励Agent提供短期记忆的调整能力，都是通过标准流程得到一定实践范围的的，完整的短期记忆。

set_message //增加tag
get_chatlogs

get_worklogs
set_worklogs //增加tag

### Memory

Memory 代表Agent的长期记忆

通过LLM驱动的Self-Think流程来更新。基本上是在根据短期记忆提炼对人、对事的看法和终结。也包含一些基于提示词工程的自我能力提升（比如复用已知的，好用的工具，或则复用自己为了解决某个特定问题已经制作并使用成功的工具）

get_contact_summary
update_contact_summary
get_sth_summary
update_sth_summary


### Workspace (TODOList)

Workspace为Agent提供了可以完成TODO的工具和保存工作结果的状态空间(FileSystem)。每个Agent默认有自己的private workspace，Workflow为Agent提供了可以共享的workspace，Workspace尽量基于文件系统构造，也方便Agent与人类协同工作。

#### Task/Todo 管理
context中需要一个隐藏的_workspace 
```
_self = parameters.get("_workspace")
```

##### agent.workspace.list_task

##### agent.workspace.create_task

```json
{
    "title": {"type": "string", "description": "The title of the task."},
    "detail": {"type": "string", "description": "The detail of the task."},
    "tags": {"type": "string array", "description": "The tags of the task."},
    "due_date": {"type": "string", "description": "The due date of the task."},
    "parent_id": {"type": "string", "description": "The parent id of the task."},
}
```

##### agent.workspace.cancel_task

```json
{
    "task_id": {"type": "string", "description": "The id of the task to cancel."},
}
```

##### agent.workspace.update_task

##### agent.workspace.get_sub_tasks

##### agent.workspace.create_todos

##### agent.workspace.list_todos

##### agent.workspace.get_todo

##### agent.workspace.update_todo

#### 核心的完成TODO的能力

##### Code Interprete

##### Send Msg (系统原生能力)

## Knowledge Base

Knowledge Base对大部分Agent来说，是一个获得私有信息,并让LLM处理结果更好的基础设施(RAG支持）。少部分Agent会使用相关API,结合Knowledge Base所服务的目标来整理Knowledge Base.

### 搜索
#### 矢量搜索
#### 传统的文本搜索搜索
#### 根据已经存在的数据库描述，构造SQL搜索

### 当成文件系统浏览


## AIGC

一系列AIGC函数，是LLM打通AIGC能力，形成新生产力的基础。

### aigc.text_2_image

文生图.返回的是生成图片的路径。

```json
{
    "prompt": "Description of the content of the painting",
}
```

### aigc.image_2_text
图生文，返回的是图片的描述
(TODO:是否需要有一个提示词来要求针对特定问题对图片进行描述)

```json
{
    "image_path": {"type": "string", "description": "image file path"}
}
```

### aigc.voice_to_text

```json
{
    "audio_file": {"type": "string", "description": "Audio file path"},
    "model": {"type": "string", "description": "Recognition model", "enum": ["openai-whisper"]},
    "prompt": {"type": "string", "description": "Prompt statement, can be None"},
    "response_format": {"type": "string", "description": "Return format", "enum": ["text", "json", "srt", "verbose_json", "vtt"]},
}
```

## system

访问当前系统的基础设施

### system.now

返回当前时间

### system.calender

保存在当前Zone上的日历，默认是与Zone Owner相关的。也可以以自动形式同步别人的日历
这个组件对AI成为个人助理非常重要，当与旧世界互通时，其细节的复杂度也是非常高的。
这是一个典型的看起来容易做起来难度很大的基础组件，是思考和验证LLM对传统软件复杂度进行降维的一个关键实践。

#### system.calender.get_events
#### system.calender.add_event
#### system.calender.delete_event
#### system.calender.update_event

### system.contacts

访问用户的联系人列表。在OOD System 中，联系人列表是非常重要的系统基础设施，为一系列的权限控制提供了基础信息。

#### system.contacts.get

通过contanct的名字得到contact的完整信息（json格式）

```json
{"name":"name"}
```

#### system.contacts.set

设置 contact 信息，注意这里使用了一个可扩展结构，我们可能需要定义一些标准的必填信息。

```json
{"name":"name","contact_info":"A json to descrpit contact"}
```

### System.shell

#### system.shell.exec

执行Shell命令（目前只支持Linux Bash）


## web

访问web的函数。使用下列函数要确保Agent有访问互联网的权限。

### web.search.duckduckgo

使用搜索引擎搜索互联网

```json
{
    "query": {"type": "string", "description": "The query to search for."}
}
```

## 常见的llm_context(能力分组)
为典型的LLM处理过程，进行了分组。主要是为了节约Token。
使用Action比使用inner function更节约。

### Process消息组 （定制度高）
得到潜在的Task并创建，在这个过程中可能需要查询已有的任务（防止重复创建）
action:craete_task, function:list_task

通常Agent在Process Message时，会表现出和其处理TODO接近的能力，核心的区别在于Process Message是立刻处理并给出结果，而变成Task更多的是当成一个异步的任务
为了能处理回复，查询历史沟通记录（寻找记忆的过程）
为了能处理回复，查询KB的过程

REMARK：目前LLM的主要问题是，如果开放的function, LLM会倾向于优先使用，是否可以做成“如果用户对答案不满意”，再使用？



### Review Task
对Task的首次执行，Review的目的
- 拆分创建TODO（使用create_todos）
- 对简单的任务立刻执行并记录更新结果 （通常是）
- 认为超出自己的能力范围，标记为无法处理或转交给合适的人（Agent） (使用update_task)
- 对已有任务进行查询（list_task,query_task）

### Do TODO(定制度高)
DO行为是复杂的，我们会精细的区分TODO的首次执行和失败后再次执行。失败后再次执行会得到之前的记录摘要，并有查询之前工作日志的能力。

Do TODO是Agent的另一个核心行为，这里会根据Agent的设定，集成更多的能力
系统为Do提供的默认支持:（按难度逐步增加）
    - 写文档 : 不需要任何外部支持
    - 运行AIGC ： AIGC的函数组
    - 收集,整理信息（通过互联网或查询知识库）： web.search.duckduckgo
    - 发送消息,系统自带，但可能需要依赖一些通讯录浏览/查找函数
    - 执行自己的代码/编写代码并执行 ： system.shell.exec，code_interprete （这是一个重点模块！）
    - 运行网络服务 ：智能合约的有通用套路，非智能合约的需要有一个完整的SOP来支持


根据任务要求保存工作成功是手动的，这里有一组workspace级别的文件系统API。
保存工作记录的行为是自动的，默认所有的Action都执行成就算是DoComplte，会自动的更新状态
有的Do可能需要自我迭代一下，这和大多数Behavor只有一次LLM调用有所不同。


### Check TODO/Task
为了解决LLM不可避免的幻视加入的Check流程。该流程会根据TODO的目标，对TODO的结果进行判定
使用 update_todo 更新TODO的状态
当所有的sub_todos都完成后，会check task的目标是否达到
当所有的sub_task都完成后，会check task的目标是否达到

因此，提供的函数主要是得到 todo/task的更深入细节的函数（访问相关log）,已经读取相关 工程成果文件 的函数

### Self-Think
获得logs 和summary
进行update




### Learning
得到logs和summary
浏览和整理KB


### Self-Improve