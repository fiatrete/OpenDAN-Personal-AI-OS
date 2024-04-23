#目录说明
## aios
系统的主要内核部分
### agent
智能体相关目录（包括agent和workflow），也是aios的关键抽象

### frame
aios的核心框架

### proto
非系统内部的，承诺长期兼容的协议定义

### enviroment
enviroment定义
其它内置的基础环境实现，包含其它非LLM AI能力的function

### knowledge
知识库相关实现

### storage
传统的存储组件

### net
基础网络库（主要是NDN，NON网络）的基础组件

## node_daemon
运行在host_os上，通过传统os概念控制aios的各个基础组件的启动。可以看成是aios的bios
aios是一个network os, 因此这个组件里还包含了最为基础的仓库实现，以支持各个组件的在线发布\安装\更新 


## component
可以按需加载的build-in组件
## service
内置的service