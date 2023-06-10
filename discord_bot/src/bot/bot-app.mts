import EventEmitter from "events"
import {
  ChannelType,
  ChatInputCommandInteraction,
  Client,
  GatewayIntentBits,
  Interaction,
  Message,
  MessageReplyOptions,
  Partials,
  REST,
  Routes,
} from "discord.js"
import { nanoid } from "nanoid"
import _ from "lodash"
import base64 from "base64-js"

import { ExchangeMessageData } from "../types/index.mjs"

interface BotAppEvents {
  message_request: (data: ExchangeMessageData) => void
}

declare interface BotApp {
  on<U extends keyof BotAppEvents>(event: U, cb: BotAppEvents[U]): this
  off<U extends keyof BotAppEvents>(event: U, cb: BotAppEvents[U]): this
  emit<U extends keyof BotAppEvents>(
    event: U,
    ...args: Parameters<BotAppEvents[U]>
  ): boolean
}

class BotApp extends EventEmitter {
  constructor(clientId: string, token: string) {
    super()

    this.clientId = clientId
    this.token = token

    this.init()
  }

  private clientId: string | undefined

  private token: string | undefined

  private client: Client | undefined

  private cachedMessages: Map<string /* message id */, Message> = new Map()

  private voiceSettings: Map<string /* chat id */, boolean> = new Map()

  private typingTexts = _.range(1, 5).map(n => `_Typing${_.repeat(".", n)}_`)

  private init = () => {
    const client = new Client({
      intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.DirectMessages,
        GatewayIntentBits.MessageContent,
      ],
      partials: [Partials.Channel],
    })

    client.on("ready", () => {
      console.log(`Logged in as ${client.user?.tag}!`)
    })

    client.on("messageCreate", this.handleMessageCreate)
    client.on("interactionCreate", this.handleInteractionCreate)

    this.client = client
  }

  private handleMessageCreate = async (message: Message) => {
    console.log("handleMessageCreate", message.author.id)
    const botId = this.client?.user?.id ?? ""
    const isExpectedMessage =
      message.author.id !== botId &&
      (message.channel.type === ChannelType.DM ||
        (message.channel.type === ChannelType.GuildText &&
          message.mentions.has(botId) === true &&
          message.mentions.everyone === false))

    if (isExpectedMessage === false) {
      return
    }

    const msgId = nanoid()
    const chatId = message.channel.id

    this.cachedMessages.set(msgId, message)
    this.emit("message_request", {
      user: {
        id: `${message.author.id}`,
      },
      chat: {
        id: chatId,
      },
      message: {
        id: msgId,
        type: "text",
        content: message.content
          .replaceAll(/@here/g, "")
          .replaceAll(/@everyone/g, "")
          .replaceAll(/\<@.*?\>/g, "")
          .trim(),
      },
      options: {
        voice: this.voiceSettings.get(chatId) ?? false,
      },
    })
  }

  private handleInteractionCreate = async (interaction: Interaction) => {
    console.log("handleInteractionCreate", interaction.isChatInputCommand())
    if (interaction.isChatInputCommand()) {
      if (interaction.commandName === "reset") {
        await this.handleCommandReset(interaction)
      }
    }
  }

  private handleCommandReset = async (
    interaction: ChatInputCommandInteraction
  ) => {
    const channelId = interaction.channel?.id
    const useId = interaction.user?.id
    if (channelId === undefined || useId === undefined) {
      return
    }

    this.emit("message_request", {
      user: {
        id: useId,
      },
      chat: {
        id: channelId,
      },
      message: {
        id: nanoid(),
        type: "clear",
        content: "",
      },
    })
    await interaction.reply("Done!")
  }

  replyMessage = async (data: ExchangeMessageData) => {
    const cachedMessage = this.cachedMessages.get(data.message.id)

    if (cachedMessage === undefined) {
      return
    }

    const { type, content } = data.message
    const replyOptions: MessageReplyOptions = {
      content: "",
      files: [],
    }

    if (type === "text") {
      replyOptions.content = content
    } else if (type === "image") {
      replyOptions.files?.push(Buffer.from(base64.toByteArray(content)))
    } else if (type === "voice") {
      replyOptions.files?.push({
        attachment: Buffer.from(base64.toByteArray(content)),
        name: `${Date.now()}.wav`,
      })
    } else if (type === "end") {
    }

    await cachedMessage.reply(replyOptions)
  }

  start = async () => {
    if (
      this.token === undefined ||
      this.clientId === undefined ||
      this.client === undefined
    ) {
      return
    }

    const commands = [
      {
        name: "reset",
        description:
          "Clear the history messages of the current session on the server.",
      },
    ]
    const rest = new REST({ version: "10" }).setToken(this.token)

    await rest.put(Routes.applicationCommands(this.clientId), {
      body: commands,
    })
    await this.client.login(this.token)
  }

  stop = () => {
    this.client?.destroy()
  }
}

export default BotApp
