export interface ExchangeMessageData {
  user: {
    id: string
  }
  chat: {
    id: string
  }
  message: {
    type: "text" | "image" | "voice" | "clear" | "end"
    content: string
    id: string
  }
  options?: {
    voice: boolean
  }
}
