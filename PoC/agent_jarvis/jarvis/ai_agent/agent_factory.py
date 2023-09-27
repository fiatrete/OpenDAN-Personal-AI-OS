from jarvis import CFG
from jarvis.ai_agent.gpt_agent import GptAgent
from jarvis.ai_agent.webui_agent import WebuiAgent
from jarvis.ai_agent.base_agent import BaseAgent
from jarvis.functional_modules.functional_module import CallerContext


def create_agent(context: CallerContext) -> BaseAgent:
    if CFG.use_private_ai:
        return WebuiAgent(context)
    else:
        return GptAgent(context)
