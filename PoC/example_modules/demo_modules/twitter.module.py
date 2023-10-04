import os

from jarvis.functional_modules.functional_module import functional_module, CallerContext
from jarvis.utils.asynchttp import do_get, do_post
from jarvis.logger import logger


def reg_or_not():
    twitter_service_address = os.getenv('DEMO_TWITTER_SERVICE_ADDRESS')
    if twitter_service_address is None or twitter_service_address.strip() == '':
        logger.warn("'DEMO_TWITTER_SERVICE_ADDRESS' is not provided, posting twitter function will not available")
        return

    @functional_module(
        name="post_tweet",
        description="post a tweet",
        signature={
            "content": {
                "type": "string",
                "description": "the content of the tweet"
            }
        })
    async def post_tweet(context: CallerContext, content: str):
        response = await do_post(twitter_service_address + "/twitter/tweet_post", '', {"content": content})
        logger.info(f"response: {response}")
        if response["type"] == 0:
            await context.reply_text(f"Failed to post, duplicate tweets cannot be sent.")
        elif response["type"] == 1:
            await context.reply_text(f"You have not authorized twitter yet, please use the link below to authorize.")
            await context.reply_text(response["authorize_url"])
        elif response["type"] == 2:
            await context.reply_text(f"Your twitter authorization has expired, please use the link below to authorize.")
            await context.reply_text(response["authorize_url"])
        elif response["type"] == 3:
            await context.reply_text(f"The tweet has been sent successfully: {response['tweet']['url']}")
        elif response["type"] == 4:
            await context.reply_text(f"Failed to post due to an unknown error.")
        else:
            pass
        return "Success"


reg_or_not()
