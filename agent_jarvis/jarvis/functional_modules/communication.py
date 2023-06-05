from jarvis.functional_modules.functional_module import functional_module, CallerContext


@functional_module(
    name="do_nothing",
    description="Do nothing. This is not an ability, just a way to let you refuse",
    signature={})
async def do_nothing(context: CallerContext):
    return "Success"
