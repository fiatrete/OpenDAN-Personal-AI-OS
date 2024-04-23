# agent memory

## memory的基本形式
memory的基本形式上是 topic+内容 
topic用一个有意义的路径表示 /xxx/xxx/xxx （有点类似脑图的逻辑，可以通过逐级展开遍历浏览所有的memory）
同一个memory可以被多个路径指向
内容则是一个json文件


## Agent 使用memory的
1. 根据当前会话的主题，尝试在known_info中加载必要的memory
2. 提供memory的 list/查询 函数， 允许agent在必要的时候 list / 查询memory
该使用逻辑的本质和kb查询逻辑很像

## Agent 更新/创建memory
1. 在任何llm process的过程中，agent都可以用写文件的形式创建memory
2. 更新memory通常是一个专门的 self-think过程，agent此时会用某种模式整理自己所有的logs和memory,并对memory进行更新、创建、删除
该更新逻辑与Agent 与KB的Self-learning逻辑很像。但根据log->summary的过程基本上是 self-think独有的

## 实现逻辑
基本思路：
1. 核心API是一组通用的文件操作API（有些场景可以是只读的） + 一组特化的对象查询API
    路径->Object，Object中包含ObjectId等信息
    ObjectId->Object
    Object一定是一个json,里面包含可以打开原始文件的路径(fileId)
2. 通过一组文件系统描述来引导Agent操作特定文件
3. 通过一组搜索API来引导Agent操作特定文件

对象查询API，基本思路是

ObjectId->Object



