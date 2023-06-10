import dotenv from "dotenv"
import path from "path"

import { ExchangeMessageData } from "../types/index.mjs"
import BotApp from "./bot-app.mjs"
import WebsocketServer from "./websocket-server.mjs"

dotenv.config({
  path: path.resolve(process.cwd(), ".env.local"),
})

class App {
  constructor() {
    // @ts-ignore
    const botApp = new BotApp(process.env.CLIENT_ID, process.env.BOT_TOKEN)
    const websocketServer = new WebsocketServer(
      parseInt(process.env.WEBSOCKET_PORT as string, 10)
    )

    botApp.on("message_request", this.handleBotAppMessageRequest)
    websocketServer.on("message_response", this.handleWebsocketMessageResponse)

    this.botApp = botApp
    this.websocketServer = websocketServer
  }

  private botApp: BotApp

  private websocketServer: WebsocketServer

  private handleBotAppMessageRequest = (data: ExchangeMessageData) => {
    console.log("handleBotAppMessageRequest", data)
    this.websocketServer.sendMessageRequest(data)
  }

  private handleWebsocketMessageResponse = (data: ExchangeMessageData) => {
    console.log("handleWebsocketMessageResponse", data.message.type)
    this.botApp.replyMessage(data)
  }

  start = () => {
    this.botApp?.start()
    this.websocketServer?.start()
  }

  stop = () => {
    this.botApp?.stop()
    this.websocketServer?.stop()
  }
}

process.on("unhandledRejection", (error: Error) => {
  console.log("unhandledRejection", error.message)
})

const app = new App()
app.start()
