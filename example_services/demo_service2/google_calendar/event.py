import datetime
from typing import Optional
from response import *
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .oauth import auth


class Event(BaseModel):
    id: str
    summary: str = ""
    description: str = ""
    start_time: int = -1  # Second
    end_time: int = -1  # Second


def convert_to_timestamp(time: str):
    return int(datetime.datetime.strptime(time, '%Y-%m-%dT%H:%M:%SZ').timestamp())


def convert_to_time(timestamp: int):
    return datetime.datetime.fromtimestamp(timestamp).isoformat() + "Z"


def convert_to_event(e: Dict):
    event = Event(**e)

    start_time = e["start"].get("dateTime", e["start"].get("date"))
    end_time = e["end"].get("dateTime", e["end"].get("date"))

    event.start_time = convert_to_timestamp(start_time)
    event.end_time = convert_to_timestamp(end_time)

    return event


def get_events():
    creds = auth()

    if not creds:
        return build_failure_response(RESPONSE_UNAUTHORIZED, [])

    try:
        service = build("calendar", "v3", credentials=creds)

        # Call the Calendar API
        now = datetime.datetime.utcnow().isoformat() + "Z"  # 'Z' indicates UTC time
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                singleEvents=True,
                orderBy="startTime",
                timeZone="UTC"
            )
            .execute()
        )
        events = events_result.get("items", [])

        if not events:
            result = build_success_response([])
        else:
            o_events = []
            for event in events:
                o_events.append(convert_to_event(event))

            result = build_success_response(o_events)

    except HttpError as error:
        print("An error occurred: %s" % error)
        result = build_failure_response(RESPONSE_UNKNOWN_ERROR[0], error.reason, [])

    return result


def get_event(event_id: str):
    creds = auth()

    if not creds:
        return build_failure_response(RESPONSE_UNAUTHORIZED, {})

    try:
        service = build("calendar", "v3", credentials=creds)

        # Call the Calendar API
        event = (
            service.events()
            .get(
                calendarId="primary",
                eventId=event_id,
                timeZone="UTC"
            )
            .execute()
        )

        if not event:
            result = build_failure_response(RESPONSE_TASK_NOT_FOUND, {})
        else:
            result = build_success_response(convert_to_event(event).dict())

    except HttpError as error:
        print("An error occurred: %s" % error)
        result = build_failure_response(RESPONSE_UNKNOWN_ERROR[0], error.reason, {})

    return result


def add_event(start_time: int, end_time: int, summary: Optional[str], description: Optional[str]):
    start = convert_to_time(start_time)
    end = convert_to_time(end_time)

    event = {
        'summary': summary,
        'description': description,
        'start': {
            'dateTime': start,
            'timeZone': 'UTC',
        },
        'end': {
            'dateTime': end,
            'timeZone': 'UTC',
        },
    }

    creds = auth()

    if not creds:
        return build_failure_response(RESPONSE_UNAUTHORIZED, [])

    try:
        service = build("calendar", "v3", credentials=creds)

        event = service.events().insert(calendarId='primary', body=event).execute()

        result = build_success_response({
            "id": event["id"]
        })

    except HttpError as error:
        print("An error occurred: %s" % error)
        result = build_failure_response(RESPONSE_UNKNOWN_ERROR[0], error.reason, [])

    return result


def delete_event(event_id: str):
    creds = auth()

    if not creds:
        return build_failure_response(RESPONSE_UNAUTHORIZED, [])

    try:
        service = build("calendar", "v3", credentials=creds)

        service.events().delete(calendarId='primary', eventId=event_id).execute()

        result = build_success_response({})

    except HttpError as error:
        print("An error occurred: %s" % error)
        result = build_failure_response(RESPONSE_UNKNOWN_ERROR[0], error.reason, [])

    return result
