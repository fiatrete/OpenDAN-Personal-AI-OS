import os
from prompt_toolkit import HTML, PromptSession, print_formatted_text
from prompt_toolkit.styles import Style
from aios.storage.storage import AIStorage
from service.aios_shell.local_compute_node_builder.local_llama_node_builder import LocalLlamaNodeBuilder
from .local_compute_node_builder import BuilderState

async def build(prompt_session: PromptSession, shell_style: Style) -> str or None:
    # model_type = await prompt_session.prompt_async(f"Please select the node server type (default: llama.cpp):", style = shell_style)

    model_type = 'llama.cpp'

    download_dir = AIStorage.get_instance().get_download_dir()
    if not os.path.exists(download_dir):
        os.mkdir(download_dir)

    state = BuilderState(prompt_session, shell_style)
    
    match model_type:
        case 'llama.cpp':
            builder = LocalLlamaNodeBuilder(state)

    while True:
        param = builder.next_parameter()
        if param is None:
            return None
        
        if state.last_result_prompt or param.desc:
            print_formatted_text(f"{state.last_result_prompt}{param.desc}", style = state.shell_style)
        value = await state.prompt_session.prompt_async(f"{param.prompt}:", style = state.shell_style)
        if value:
            value = value.strip()

        state.params[param.name] = value
        url = await param.applier.apply(state, param.name, value)

        if url is not None:
            return url