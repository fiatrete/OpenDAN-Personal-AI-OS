import os

from jarvis.functional_modules.functional_module import functional_module, CallerContext
from jarvis.logger import logger
from jarvis.utils.asynchttp import do_get, do_post


def reg_or_not():
    youtube_service_address = os.getenv("DEMO_YOUTUBE_SERVICE_ADDRESS")
    if youtube_service_address is None or youtube_service_address.strip() == '':
        logger.warn("'DEMO_YOUTUBE_SERVICE_ADDRESS' is not provided, youtube related functions will not available")
        return

    @functional_module(
        name="youtube_video_brief",
        description="Get the brief content of a youtube video",
        signature={
            "url": {
                "type": "string",
                "description": "The address of the video" 
            }
        })
    async def youtube_video_brief(context: CallerContext, url: str):
        await context.push_notification(f"One second... I'm watching this video: {url}")
        if not url.startswith('https://www.youtube.com/watch?') and not url.startswith("https://youtu.be/"):
            await context.reply_text("Sorry, failed to determine which video to watch.")
            return "Failed"
        response = await do_get(youtube_service_address + "/videos/summary",
                                params={"url": url, "open_summary": "true"})

        has_result = False
        for info in response.values():
            summary = info['summary']
            if len(summary) > 0:
                has_result = True
                await context.reply_text(f"The brief content of this video: \n\n{summary}")
                break
        if not has_result:
            await context.reply_text("Sorry, failed to get the video content.")
            return "Failed"
        return summary

    @functional_module(
        name="youtube_video_brief_vid",
        description="Get the brief content of a youtube video identified by video id",
        signature={
            "video_id": {
                "type": "string",
                "description": "The video id of the video"
            }
        })
    async def youtube_video_brief_vid(context: CallerContext, video_id: str):
        url = f'https://www.youtube.com/watch?v={video_id}'
        await context.push_notification(f"One second... I'm watching this video: {url}")
        response = await do_get(youtube_service_address + "/videos/summary",
                                params={"video_id": video_id, "open_summary": "true"})
        for info in response.values():
            summary = info['summary']
            if len(summary) == 0:
                await context.reply_text(f"Sorry, failed to get it's summary.")
            else:
                await context.reply_text(f"The brief content of this video: \n\n{summary}")
            break
        return summary

    async def youtube_latest_video_info_of(context: CallerContext, username: str, open_summary: bool):
        if username.startswith('@'):
            username = username[1:]
        if open_summary:
            await context.push_notification(f"One second... I'm watching the newest videos of {username}")
        else:
            await context.push_notification(f"One second... I'm looking for the newest videos of {username}")
        response = await do_get(youtube_service_address + "/videos/summary",
                                params={"username": username, "open_summary": "true" if open_summary else "false"})
        for item in response.values():
            item['published_at'] = item['published_at'].replace(
                'T', ' ').replace('Z', ' UTC')
        return response

    @functional_module(
        name="youtube_x_video_info",
        description="Get the basic information of a youtube user's newest videos, when the summary of videos are not required, you should use this function",
        signature={
            "username": {
                "type": "string",
                "description": "The username"
            }
        })
    async def youtube_x_video_info(context: CallerContext, username: str):
        response = await youtube_latest_video_info_of(context, username, False)
        result = f'The brief content of the latest videos of {username} are:\n'
        result_to_gpt = "| id | date | title |\n|----|----|----|"
        for info in sorted(response.values(), key=lambda d: d['published_at'], reverse=True):
            result += f"\n· {info['published_at']}, {info['title']}"
            result_to_gpt += f"\n| {info['video_id']} | {info['published_at']} | {info['title']} |"
        logger.debug(f"Latest videos:\n{result}")
        await context.reply_text(result)
        # Reply this to GPT, then GPT is able to known the correcponding video ID.
        return result_to_gpt

    @functional_module(
        name="youtube_notify_new",
        description="Watching an Youtuber, push an notification when the youtuber published a new video",
        signature={
            "username": {
                "type": "string",
                "description": "The username"
            }
        })
    async def youtube_notify_new(context: CallerContext, username: str):
        if username.startswith('@'):
            username = username[1:]
        users = await do_post(youtube_service_address + "/timer-task/add", '', params={"username": username})
        msg = "Done! I will notify you once these youtuber(s) upload new videos:\n\n- " + '\n· '.join(
            users)
        await context.reply_text(msg)
        return "Success"

    @functional_module(
        name="youtube_list_notifies",
        description="Query the youtuber list being watched",
        signature={})
    async def youtube_list_notifies(context: CallerContext):
        users = await do_get(youtube_service_address + "/timer-tasks")
        if len(users) > 0:
            msg = "I will notify you once any of the following youtuber(s) upload new videos:\n\n- " + '\n· '.join(
                users)
        else:
            msg = "You has not been watching any youtuber."
        await context.reply_text(msg)
        return "Success"


reg_or_not()
