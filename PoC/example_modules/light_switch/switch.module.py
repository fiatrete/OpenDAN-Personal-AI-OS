from jarvis.functional_modules.functional_module import functional_module, CallerContext


@functional_module(
    name="toggle_light",
    description="Turn on/off the light.",
    signature={
        "room": {
            "type": "string",
            "description": "The room name"
        },
        "on": {
            "type": "boolean",
            "description": "Turn on or off"
        }
    })
async def light_switch(context: CallerContext, room: str, on: bool):
    # Do the actual control here, something like this
    # room_id = convert_room_name_to_id(room)
    # await control_unit.toggle_light(room_id, on)

    await context.reply_text("The light in " + room + " has turn " + ("on" if on else "off"))
    return "Success"
