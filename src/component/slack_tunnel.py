import asyncio

from slack_bolt.adapter.socket_mode.websockets import AsyncSocketModeHandler
from slack_bolt.app.async_app import AsyncApp

from aios.frame.tunnel import AgentTunnel
from aios.proto.agent_msg import AgentMsg


class SlackTunnel(AgentTunnel):
    type: str
    token: str
    app_token: str

    def __init__(self):
        super().__init__()
        self.type = "SlackTunnel"
        self.token = ""

    @classmethod
    def register_to_loader(cls):
        async def load_slack_tunnel(config: dict) -> AgentTunnel:
            result_tunnel = SlackTunnel()
            if await result_tunnel.load_from_config(config):
                return result_tunnel
            else:
                return None

        AgentTunnel.register_loader("SlackTunnel", load_slack_tunnel)

    async def load_from_config(self, config: dict) -> bool:
        self.target_id = config["target"]
        self.tunnel_id = config["tunnel_id"]

        self.type = "SlackTunnel"
        self.token = config["token"]
        self.app_token = config["app_token"]

        return True

    def post_message(self, msg: AgentMsg) -> None:
        pass

    async def start(self) -> bool:
        app = AsyncApp(token=self.token)

        @app.event("message")
        async def _handle_message(event, say):
            await self._process_message(event)

        asyncio.create_task(AsyncSocketModeHandler(app, self.app_token).start_async())
        return True

    async def close(self) -> None:
        pass

    async def _process_message(self, msg: AgentMsg) -> None:
        return
