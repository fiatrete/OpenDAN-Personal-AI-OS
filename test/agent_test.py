import sys
sys.path.append('../src/component/')

from agent_manager import agent_manager

def clean_agent():
    print("clean_agent")
    
def clean_agent_templete():
    print("clean_agent_templte")

def test_agent():
    am = agent_manager()
    am.initial("root_dir")
    agent = am.get("english_teacher")
    if agent is None:
        agent_templete = am.get_templete("english_teacher")
        
        if agent_templete is None :
            op = am.install("english_teacher")
            #wait install done
        
        agent = am.create(agent_templete,"Tracy","Wang","Tracy Wang is my english teacher")
    
    print("Agent Tracy Wang load success!");
    print(agent.get_introduce());

      

    #chat_session = agent.get_default_chat_session("master");
    #chat_session.chat("给我讲一个英文笑话!");
    #chat_session.wait_response();
    #print(chat_session.last_msg());

if __name__ == "__main__":
    test_agent()