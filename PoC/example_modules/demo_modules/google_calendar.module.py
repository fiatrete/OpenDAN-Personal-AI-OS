import datetime
import os
from typing import List

from jarvis.functional_modules.caller_context import CallerContext
from jarvis.functional_modules.functional_module import functional_module
from jarvis.logger import logger
from jarvis.utils.asynchttp import do_get, do_post


def reg_or_not():
    google_calendar_service_address = os.getenv('DEMO_GOOGLE_CALENDAR_SERVICE_ADDRESS')
    if google_calendar_service_address is None or google_calendar_service_address.strip() == '':
        logger.warn(
            "'DEMO_GOOGLE_CALENDAR_SERVICE_ADDRESS' is not provided, google calendar function will not available")
        return

    @functional_module(
        name="add_alarm",
        description="Create an alarm",
        signature={
            "date": {
                "description": "The alarm date, 'YYYY-mm-dd HH:MM:SS format'",
                "type": "string",
                "required": True
            },
            "desc": {
                "description": "The event description",
                "type": "string",
                "required": True
            }
        })
    async def add_alarm(context: CallerContext, date, desc):
        # date = "2023-05-10 14:56:59"
        now = datetime.datetime.strptime(date, "%Y-%m-%d %H:%M:%S").timestamp()
        # even we modify the tz of datetime, the timestamp does not change (stays to be UNIX timestamp with an offset).
        # so we adjust the timestamp mannually
        now -= context.get_tz_offset() * 3600
        result = await do_post(google_calendar_service_address + "/task/add", {
            "start_time": now,
            "end_time": now,
            "summary": desc,
            "description": desc
        })
        if not isinstance(result, dict):
            await context.reply_text("Sorry, failed to access calendar")
            return "Failed to access calendar"
        if result["code"] == 200:
            await context.reply_text(f"Alarm have been added: {desc} as {date}")
            return "Success"
        await context.reply_text(f"Sorry, failed to access calendar: {result['message']}")
        return result["message"]

    @functional_module(
        name="delete_alarm",
        description="delete all alarms whose ID is in the list",
        signature={
            "IDs": {
                "type": "array",
                "items": { "type": "string" },
                "description": "A list of alarm IDs to delete",
                "required": True
            }
        })
    async def delete_alarm(context: CallerContext, IDs: List[str]):
        # get all tasks
        result = await do_get(google_calendar_service_address + "/tasks")
        if not isinstance(result, dict):
            await context.reply_text("Sorry, failed to access google calendar")
            return "Failed to query google calendar"
        if result["code"] != 200:
            await context.reply_text(f"Sorry, failed to access google calendar: {result['message']}")
            return result["message"]
        items = result["data"]
        if len(items) == 0:
            await context.reply_text("Sorry, you don't have any alarm now.")
            return "Canceled"

        deleted = []
        all_event_ids = [item['id'] for item in items]
        for alarm_id in IDs:
            if alarm_id not in all_event_ids:
                continue
            # delete
            result = await do_post(google_calendar_service_address + f"/task/delete/{alarm_id}", "")
            if not isinstance(result, dict):
                logger.log(f"Failed to delete alarm: {alarm_id}")
                continue
            if result["code"] != 200:
                logger.log(
                    f"Failed to delete alarm: {alarm_id}: {result['message']}")
                continue
            deleted.append(alarm_id)

        if len(deleted) == 0:
            await context.reply_text("Sorry, failed to delete calendar event")
            return "Failed"

        msg = "These alarms are deleted:"
        for alarm_id in deleted:
            for item in items:
                if item['id'] == alarm_id:
                    msg += f'\n{item["summary"]}'
                    break
        await context.reply_text(msg)
        return "Success"

    @functional_module(
        name="query_alarm",
        description="query all existing alarm",
        signature={})
    async def query_alarm(context: CallerContext):
        result = await do_get(google_calendar_service_address + "/tasks")
        if not isinstance(result, dict):
            await context.reply_text("Sorry, failed to access google calendar")
            return "Failed to query google calendar"
        if result["code"] == 200:
            if len(result['data']) > 0:
                markdown = 'Here is your calendar:\n'
                # Reply a simplified version of md to GPT.
                # Ensure GPT is notified.
                markdown_to_gpt = '| ID | Date | Event |\n|----|----|----|'
                for item in result['data']:
                    timestamp = item["start_time"] + context.get_tz_offset() * 3600
                    time_str = datetime.datetime.fromtimestamp(
                        timestamp).strftime("%Y-%m-%d %H:%M:%S")
                    markdown += f'\n· {time_str} UTC{context.get_tz_offset_str()}, {item["summary"]}'
                    markdown_to_gpt += f'\n| {item["id"]} | {time_str} | {item["summary"]} |'
                await context.reply_text(markdown)
                return markdown_to_gpt
            else:
                await context.reply_text("You don't have any calendar event.")
                return "Success"
        await context.reply_text(f"Sorry, failed access google calendar: {result['message']}")
        return result["message"]


reg_or_not()
