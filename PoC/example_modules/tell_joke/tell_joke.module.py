from jarvis.functional_modules.functional_module import functional_module, CallerContext

import joke_db


@functional_module(
    name="tell_joke",
    description="Tell a joke. DO NOT come up with a joke if you call this function, this module will tell one.",
    signature={})
async def do_nothing(context: CallerContext):
    the_joke = joke_db.random_joke()
    await context.reply_text(the_joke)
    return the_joke
