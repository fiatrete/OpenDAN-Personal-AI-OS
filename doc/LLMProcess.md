# LLMProcess

设计目的是理解到 提示词=>LLM=>LLM Result 的过程是系统的核心复杂度。Agent的粒度太大了，需要更合适的设计来封装这个复杂度，并给予这个过程更大的灵活性和可组合型。并更易于构建测试

比如
1. 可以很容易的组合两个已知的LLM Process（上一个的输出是下一个的输入），这个设计有一点类似LangChain (我们在正式系统中，肯定允许整个Agent都用LangChain来构建)
2. 可以用用一个LLM Process来构建另一个LLM Process的Prompt
3. 继承一个复杂的LLM Process，进行简单配置，就可以得到一个新的LLM Process。这个新的LLM Process可以享受到复杂LLM Process持续迭代的好处
4. 有一些常用的，系统内置的LLM Process可以从配置文件中加载。

```python
def agent.on_process_message():
    llm_process = self.on_message_llm_process.clone()
    llm_result = llm_process.do()
    


```