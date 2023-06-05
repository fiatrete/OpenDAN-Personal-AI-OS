const express = require("express");
const app = express();
const http = require("http");
const server = http.createServer(app);
const { Server } = require("socket.io");
const io = new Server(server, {
  maxHttpBufferSize: 50000000,
});
const readline = require("readline");
const { randomBytes } = require("crypto");

app.get("/", (req, res) => {
  res.sendFile(__dirname + "/index.html");
});

io.on("connection", (socket) => {
  console.log("a user connected");
  let isRunning = true;
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  socket.on("disconnect", (reason) => {
    isRunning = false;
    rl.close();
    console.log("Client disconnected: ", reason);
  });
  socket.on("chat_message", (msg) => {
    console.log("Received: ", msg);
  });

  async function readLine() {
    return new Promise((resolve) => {
      rl.question("Input: ", (answer) => {
        resolve(answer);
      });
    });
  }

  async function readLoop() {
    while (isRunning) {
      let input = await readLine();
      socket.emit("chat_message", {
        user: {
          id: "user_id",
        },
        chat: {
          id: "session_id",
        },
        message: {
          type: "text",
          content: input,
          id: `${Math.random() * 1000}`,
        },
      });
    }
  }

  readLoop();
});

server.listen(3000, () => {
  console.log("listening on *:3000");
});
