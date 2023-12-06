import copy

from aios.agent.agent_base import CustomAIAgent, LLMPrompt
from aios.knowledge.data.writer import split_text
from aios.proto.agent_msg import AgentMsg, AgentMsgType
from aios.proto.compute_task import ComputeTaskResultCode


class TextSummaryAgent(CustomAIAgent):
    def __init__(self):
        super().__init__("TextSummary", "Text Summary", 128000)

    async def _process_msg(self, msg: AgentMsg, workspace=None) -> AgentMsg:
        if msg.msg_type is not AgentMsgType.TYPE_MSG:
            return AgentMsg.create_error_resp(msg, "only support msg type")

        if msg.body_mime is not None and msg.body_mime != "text/plain":
            return AgentMsg.create_error_resp(msg, "only support text/plain mime type")

        chunks = split_text(msg.body, separators=["\n\n", "\n"], chunk_size=4000, chunk_overlap=200, length_function=len)

        prompt = LLMPrompt()
        prompt.system_message = "Your job is to generate a summary based on the input."
        if len(chunks) == 1:
            prompt.append(LLMPrompt(chunks[0]))
            resp = await self.do_llm_complection(prompt)
            if resp.result_code != ComputeTaskResultCode.OK:
                return msg.create_error_resp(resp.error_str)
            return msg.create_resp_msg(resp.result_str)

        segments = []
        for i, chunk in enumerate(chunks):
            seg_prompt = copy.deepcopy(prompt)
            seg_prompt.append(LLMPrompt(chunk))
            resp = await self.do_llm_complection(seg_prompt)
            if resp.result_code != ComputeTaskResultCode.OK:
                return msg.create_error_resp(resp.error_str)
            segments.append(resp.result_str)

        segments_str = "\n".join(segments)
        prompt.append(LLMPrompt(f"以下文本分段之后的各段摘要，请合并生成一个完整摘要：\n{segments_str}"))
        resp = await self.do_llm_complection(prompt)
        if resp.result_code != ComputeTaskResultCode.OK:
            return msg.create_error_resp(resp.error_str)
        return msg.create_resp_msg(resp.result_str)


def init():
    return TextSummaryAgent()
