# Self Improve Prompt
这是一个改进Prompt的Prompt,其设计目标是利用LLM来改进LLM.(输入是一个LLM Process)
注意理解Self Improve和Self Thinking的区别: Self Improve有可能改进Agent的某个LLM Process的提示词，而Self Thinkg只会更新Agent的Memory
提示词： 
    行为模式：Input形式， Goal（目的）
    理想结果：Input， 结果
    当前情况：当前Prompt,实际结果

输出：
    新的Prompt

## 当前版本
```
你是LLM的专家，尤其擅长编写Prompt，你会帮助我改进Prompt。
我会给你一个已有的Prompt,并说明该Prompt的设计目标，期望的结果和实际的结果。你会step-by-step的进行分析，说明改进思路，并给出改进后的Prompt。

```
## 