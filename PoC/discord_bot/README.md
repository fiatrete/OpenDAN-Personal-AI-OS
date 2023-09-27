# Jarvis Discord Bot

## What is Jarvis Discord Bot?

Using Jarvis Discord Bot you can interact with Jarvis through Discord app on various devices and share him with your friends. In the early versions of Jarvis, you could only interact with Jarvis through a simple web page. This limited your interaction with Jarvis to computers and browsers, and you had to be on the same local network.

## How to setup

### Creating a Discord App and Bot Account

- Register a Discord account if you don't have one yet.
- Login to the Discord website https://discord.com/.
- Go to the Discord Developer Portal https://discord.com/developers/applications/.
- Click the `New Application` button in the top right corner.
- Give your application a name, and select `Create`.
- From the left-hand menu, select the `Bot` option, then configure your bot's name and icon.
- Turn the `Public Bot` switch to `On`.
- Turn the `PRESENCE INTENT` switch to `On`.
- Turn the `MESSAGE CONTENT INTENT` switch to `On`.
- Copy the `Token` string, you will need it later.

### Adding the Bot to a Server

- From the left-hand menu, select `OAuth2`.
- Copy the `CLIENT ID` string, you will need it later.
- Click on `URL Generator`, Under `Scopes`, check the `bot` box.
- Configure the `Bot Permissions` as required, ensuring that at least `Send Messages` and `Use Slash Commands` are checked.
- Copy and paste the auto-generated URL into your web browser.
- Select the server you want to add the bot to.
- Verify yourself with `I am not a robot`.
- Click `Authorize` to complete the process of adding the bot to the server.

### Running the bot

- cd to the root directory of the bot(which contains this README.md file).
- Before the first running, you need to configure some parameters:
  - copy the `.env.template` file to `.env.local`.
  - Copy and paste the previously obtained `Token` and `CLIENT ID` into the `.env.local` file.
  - run `npm install`.
- run `npm run start:bot`.

NOTE: You need to set `JARVIS_SERVER_MODE=false` and `JARVIS_BOT_SERVER_URL="http://localhost:10000"` in the Jarvis's `.env` file
### Running the bot in docker
```
# build docker image
docker build -t jarvis-discord-bot .

docker run -d --name jarvis-discord-bot \
-e CLIENT_ID='Your Client ID' \
-e BOT_TOKEN='Your Bot Token' \
-e WEBSOCKET_PORT=10000 \
jarvis-discord-bot:latest
```