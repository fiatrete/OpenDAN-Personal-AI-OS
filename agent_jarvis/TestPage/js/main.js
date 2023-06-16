(() => {
  // Utils
  function scrollElementToEnd(ele) {
    ele.scrollTop = ele.scrollHeight;
  }

  let messageIdCounter = 0;
  function makeChatMessage(messageContent, messageType) {
    return JSON.stringify({
      user: {
        id: "FakeUserID",
      },
      chat: {
        id: "FakeChatID",
      },
      message: {
        type: messageType,
        content: messageContent,
        id: `FakeMessageID_${messageIdCounter++}`,
      },
    });
  }

  let socketIoAddr = document.location.origin;
  let socket = io(socketIoAddr);
  let status = document.getElementById("status");
  let input = document.getElementById("input");
  let sendButton = document.getElementById("send_button");
  let resetButton = document.getElementById("reset_button");
  let testButton = document.getElementById("test_button");

  let testContentArray = [
    "What's the date today?",
    "Who are you?",
    "What technology are you based on?",
    "Generate a picture of a panda.",
    "I need the panda in a house.",
    "Tell me about the newest videos of @tiabtc.",
    "Give me a summary of the latest video above.",
    "What this video is talking about: https://www.youtube.com/watch?v=HtcPWORWJ1U",
    "Remind me to go shopping tomorrow 6pm.",
    "What reminders do I currently have?",
    "Tweet out: Hello, this is a message from AI.",
  ]
  const mdCvt = new showdown.Converter({
    tables: true,
  });

  function appendChatItem(who, msg) {
    let item = document.createElement("li");
    if (who == "me") {
      item.classList.add("align_right");
    }
    item.innerHTML = msg;
    messages.appendChild(item);
    scrollElementToEnd(messages);
  }

  let isProcessing = false;
  let notification = "";
  function startProcessing() {
    notification = "";
    isProcessing = true;

    let dotCount = 0;

    scrollElementToEnd(messages);

    let inter = setInterval(() => {
      if (!isProcessing) {
        status.classList.add("hidden");
        clearInterval(inter);
        return;
      }
      status.classList.remove("hidden");
      status.innerHTML = notification;
      if (notification.length > 0) {
        status.innerHTML += "<br/>";
      }
      status.innerHTML += "Processing";
      for (let i = 0; i < dotCount; ++i) {
        status.innerHTML += ".";
      }
      dotCount += 1;
      if (dotCount == 4) {
        dotCount = 0;
      }
    }, 500);
  }
  function stopProcessing() {
    isProcessing = false;
  }

  socket.on("chat_message", (msg) => {
    if (typeof(msg) !== 'object') {
      console.log("Expecting object, got: ", msg);
      return;
    }
    let msgType = msg.message.type;
    let msgContent = msg.message.content;
    switch (msgType) {
      case "text":
        msgContent = msgContent.replaceAll('\n', '<br/>');
        console.log("text message: " + msgContent);
        appendChatItem("remote", msgContent);
        break;
      case "image": {
        var item = document.createElement("li");
        item.innerHTML = `<img src="data:image/png;base64,${msgContent}" alt="Image" class="replied-img">`;
        messages.appendChild(item);
        scrollElementToEnd(messages);
        break;
      }
      case "markdown": {
        const item = document.createElement("li");
        console.log(msgContent);
        item.innerHTML = mdCvt.makeHtml(msgContent);
        messages.appendChild(item);
        scrollElementToEnd(messages);
        break;
      }
      case "notification": {
        notification = msgContent;
        break;
      }
      case "end": {
        stopProcessing();
        break;
      }
    }
  });
  socket.on("connect", () => {
    let tzOffset = `${-new Date().getTimezoneOffset()/60}`;
    socket.emit("chat_message", makeChatMessage(tzOffset, 'set_ts_offset'));
  });
  socket.on("disconnect", (reason) => {
    console.log("Disconnect due to: ", reason)
  });

  function submitMessage() {
    if (input.value) {
      socket.emit(
        "chat_message",
        makeChatMessage(input.value, 'text')
      );
      appendChatItem("me", input.value);
      startProcessing();
      input.value = "";
    }
  }
  sendButton.addEventListener('click', function (e) {
    submitMessage();
  });
  resetButton.addEventListener('click', function(e) {
    socket.emit('chat_message', makeChatMessage('', 'clear'));
    stopProcessing();
    messages.innerHTML = "";
  })
  testButton.addEventListener('click', function(e) {
    let index = 0;
    let isWaitingForResponse = false;
  
    function sendNextMessage() {
      if (index < testContentArray.length && !isWaitingForResponse) {
        input.value = testContentArray[index];
        submitMessage();
        index++;
        isWaitingForResponse = true;
      }
    }
  
    socket.on("chat_message", function(msg) {
      if (isWaitingForResponse) {
        if (msg.message.type === 'end') {
          isWaitingForResponse = false;
          sendNextMessage();
        } else {
          // Jarvis have not finish his reply, just wait
        }
      }
    });
  
    sendNextMessage();
  });

  input.addEventListener('keyup', function (e) {
    if (e.key === 'Enter') {
      submitMessage();
    }
  })
})();
