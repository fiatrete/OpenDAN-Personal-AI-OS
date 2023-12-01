from abc import abstractmethod

from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style

class BuilderState:
    def __init__(self, prompt_session: PromptSession, shell_style: Style):
        self.prompt_session = prompt_session
        self.shell_style = shell_style
        self.next_step = 0
        self.last_result_prompt = ""
        self.params = {}

# class ApplyResult:
#     def __init__(self, next_step: any, url: str or None = None, result_prompt: str or None = None) -> None:
#         self.next_step = next_step
#         self.url = url
#         self.result_prompt = result_prompt


class ParameterApplier:
    @abstractmethod
    async def apply(self, state: BuilderState, name: str, value: str or None = None) -> str or None:
        pass

class BuildParameter:
    def __init__(self, name: str, applier: ParameterApplier, desc: str or None = None, default_value: str or None = None):
        self.name = name
        self.desc = desc
        self.default_value = default_value
        self.applier = applier

class LocalComputeNodeBuilder:
    def __init__(self, state: BuilderState) -> None:
        self.state = state

    @abstractmethod
    def next_parameter(self) -> BuildParameter or None:
        pass