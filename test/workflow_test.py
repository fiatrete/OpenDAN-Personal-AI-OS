

def test_workflow():
    
    
    pass


async def _test_llm_parser():
    test_llm_result = """
# Foggie with AI Agent
1.已经完成了基础系统改造，只要Foggie能安装docker image就可以实现集成
2.安装后，用户需要提供OpenAI Token和TG Bot Token，就可以构建自己的私有AI机器人（也可以通过绑定email实现智能邮件客服）
   我们也可以用自己的OpenAI Token给用户用，但这需要设计新的商品。OpenAI Token用起来还是挺贵的
3.已在发布前夕，目前集成测试的主要问题是对Email和个人文件的AI分析需要比较强的性能。

# DMC开源挖矿软件
正在等待解决 Order Placement Issue


# Foggie with AI Agent
1. We have completed the basic system transformation. As long as Foggie can install the docker image, integration can be achieved.
2. After installation, users need to provide an OpenAI Token and TG Bot Token to build their own private AI robot. This can also be accomplished by linking an email to implement an intelligent email customer service. We could use our own OpenAI Token for users, but this would require the design of a new product. Using the OpenAI Token can be quite costly.
3. We are on the eve of launch. The main issue in our integrated testing currently is that AI analysis of emails and personal files requires substantial performance, and the results don't seem so smart.

#DMC Open Source Mining Software
We are waiting to resolve the Order Placement Issue.

##/send_msg "xxx xxx"
abcdcdsdf
sfsadfasdf 
# Foggie with AI Agent
1. We have completed the basic system transformation. As long as Foggie can install the docker image, integration can be achieved.
2. After installation, users need to provide an OpenAI Token and TG Bot Token to build their own private AI robot. This can also be accomplished by linking an email to implement an intelligent email customer service. We could use our own OpenAI Token for users, but this would require the design of a new product. Using the OpenAI Token can be quite costly.
3. We are on the eve of launch. The main issue in our integrated testing cur

##/call abcd "xxx xxx"
"""
    llm_result = Workflow.prase_llm_result(test_llm_result)
    assert len(llm_result.calls) == 1
    assert len(llm_result.send_msgs) == 1
    print(llm_result)