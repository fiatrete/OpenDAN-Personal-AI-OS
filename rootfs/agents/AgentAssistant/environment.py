import logging
from typing import Optional

import toml

from aios_kernel import Environment, SimpleAIFunction
import os


local_path = os.path.split(os.path.realpath(__file__))[0]

logger = logging.getLogger(__name__)


class AgentAssistantEnvironment(Environment):
    def __init__(self):
        super().__init__("agent_assistant_env")
        self.add_ai_function(SimpleAIFunction("read_agent",
                                              "Read the agent with the specified name",
                                              self.read_agent,
                                              {"agent_id": "The id of the agent to be read"}))
        self.add_ai_function(SimpleAIFunction("save_agent",
                                              "save the agent with the specified name",
                                              self.save_agent,
                                              {"agent_id": "The id of the agent to be saved",
                                                          "agent_data": "The toml data of the agent to be saved",
                                                          "is_new": "Whether to create a new agent, The value is true if it is created, and it is false if it is modified."}))

    def _do_get_value(self, key: str) -> Optional[str]:
        pass

    async def read_agent(self, agent_id: str) -> str:
        agent_dir = os.path.join(local_path, "..", agent_id)
        if not os.path.exists(agent_dir):
            return "exec failed.agent is not exists."

        with open(os.path.join(agent_dir, "agent.toml"), "r", encoding='utf-8') as f:
            agent_data = f.read()

        return "exec success. agent data:\n" + agent_data

    async def save_agent(self, agent_id: str, agent_data: str, is_new: str) -> str:
        logger.info(f"save_agent: {agent_id} {agent_data}")

        agent_dir = os.path.join(local_path, "..", agent_id)
        if os.path.exists(agent_dir) and is_new == "true":
            return "exec failed.agent already exists, please change the agent id and try again."

        if not os.path.exists(agent_dir):
            os.mkdir(agent_dir)

        with open(os.path.join(agent_dir, "agent.toml"), "w", encoding='utf-8') as f:
            f.write(agent_data)

        return "exec success."


def init():
    return AgentAssistantEnvironment()
