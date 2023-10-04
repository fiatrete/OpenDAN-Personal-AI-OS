import { createServer, Server as HTTPServer } from "http"
import { Server as SocketIOServer, Socket } from "socket.io"
import express from "express"
import EventEmitter from "events"

import { ExchangeMessageData } from "../types/index.mjs"

interface WebsocketServerEvents {
  message_response: (data: ExchangeMessageData) => void
}

declare interface WebsocketServer {
  on<U extends keyof WebsocketServerEvents>(
    event: U,
    cb: WebsocketServerEvents[U]
  ): this
  off<U extends keyof WebsocketServerEvents>(
    event: U,
    cb: WebsocketServerEvents[U]
  ): this
  emit<U extends keyof WebsocketServerEvents>(
    event: U,
    ...args: Parameters<WebsocketServerEvents[U]>
  ): boolean
}

class WebsocketServer extends EventEmitter {
  constructor(port: number) {
    super()

    const app = express()
    const httpServer = createServer(app)
    const sioServer = new SocketIOServer(httpServer, {
      maxHttpBufferSize: 50 * 1024 * 1024,
      pingInterval: 25000,
      pingTimeout: 20000,
    })

    sioServer.on("connect", this.handleConnect)

    this.port = port
    this.httpServer = httpServer
    this.sioServer = sioServer
  }

  private port: number

  private httpServer: HTTPServer

  private sioServer: SocketIOServer

  private handleConnect = (socket: Socket) => {
    console.log("handleConnect", socket.id)

    socket.on("disconnect", (reason: string) => {
      console.log("socket disconnect", reason, Date.now())
    })
    socket.on("chat_message", (data: ExchangeMessageData) => {
      this.emit("message_response", data)
    })
  }

  sendMessageRequest = (data: ExchangeMessageData) => {
    this.sioServer.emit("chat_message", data)
  }

  start = () => {
    this.httpServer.listen(this.port, () => {
      console.log(`listening on *:${this.port}`)
    })
  }

  stop = () => {
    this.sioServer.close()
  }
}

export default WebsocketServer
