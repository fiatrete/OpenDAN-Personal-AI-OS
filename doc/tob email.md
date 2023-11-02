# issue tree
最核心的机制是树状的issue管理，一个issue应当包含以下属性：
+ 谁提出来的
+ 分配给谁的，如果有的话
+ 起始日期
+ deadline，如果有的话
+ 在哪个邮件里面提出的，引用某个email的原始链接
+ 这个issue的summary，有几种情况，
    + 一个新的任务，要达成什么目标
    + 提出了一个问题，需求答案
    + 解决了某个issue，完成了task或者解答了一个问题
+ 推断出来的 issue的状态，进行中，关闭，超时，完成了
+ parent issue

knowledge维护一个issue tree，从一个root issue出发（root可以是抽象的，比如一个组织的存在，并不是具体的）；knowledge env 提供对这个issue tree的维护接口：
+ 新增issue
+ 更新issue

# parse email
假定从从某个起始日期开始，以每天为单位，扫描当天新增的email，对每封email：
1. 输入email 和 从knowledge base获取 issue tree
2. llm提示词应当包括：issue tree， email正文， knowledge env， llm完成如下推理：
+ email正文提出了一个新的issue，在knowledge env新增issue
+ email正文改变了一个issue的状态
    + 通报完成了一个task
    + 回答了一个问题
    + 明确改变一个issue的状态：认为完成，要延期，认为要取消
+ 根据推理结果正确产生knowledge env 的调用，更新issue tree的状态

## 推理部分可能的out of token：
1. 裁剪掉已经关闭，超时的 issue
2. 根据标题特征，是不是对某个email的回复，定位到某个issue， 裁剪出 sub tree
2. 很长的邮件正文：
    1. 第一种方法：先llm推理email的summary，再把summary当正文输入推理issue
    2. 第二种方法（我觉得更好）：分片迭代输入email正文，单次llm推理的提示词就变成：issue tree， 当前email summary， 当段email正文，knowledge env：
        + env里面新增一个method，更新当前email summary


# build issue tree
## 第一种结构：基于knowledge pipeline
1. pipeline input： 判定当前时间晚于 起始时间并且早于下一个自然天，开始爬正确范围内的邮件输入
2. pipeline parser：包含准备user prompt 的计算部分，和几个agent
+ 计算部分： 裁剪issue tree，[可选的：调用llm推理生成summary]
+ agent 部分：
    + agent提示词：从输入的结构化issue tree， 和邮件正文，回复对issue tree knowledge env的调用
    + 输入提示词： email 正文或者summary，裁剪后的issue tree
+ parser的流程：
    对每一个输入的email，查询（裁剪）当前issue tree，把email 和 issue tree 当作user prompt发送给agent，等待agent返回


## 第二种结构：基于agent workspace（待定）
1. schedule task：在每一天产生一个build issue tree task
2. build issue tree agent: 响应build issue tree task（可不可以以计算为入口，还是只能agent入口）
+ agent调用email env，读出一封邮件
+ agent调用knowledge env，返回issue tree
+ agent从邮件内容和issue tree推理，回复对issue tree knowledge env 的调用

# query issue tree
主动的或者被动的根据当前issue tree的状态，推理出一些汇总的结论：
+ 是不是有超期的事项
+ 事情是不是有在推进
+ 有哪些事情完成了