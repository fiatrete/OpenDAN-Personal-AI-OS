import os
import random
import subprocess
import requests

from prompt_toolkit import print_formatted_text
from prompt_toolkit.shortcuts import ProgressBar
from prompt_toolkit.formatted_text import FormattedText
from aios_kernel.compute_kernel import ComputeKernel
from aios_kernel.compute_node_config import ComputeNodeConfig
from aios_kernel.local_llama_compute_node import LocalLlama_ComputeNode

from aios_kernel.storage import AIStorage
from .local_compute_node_builder import BuildParameter, BuilderState, LocalComputeNodeBuilder, ParameterApplier

class BuildParameterModelPath:
    async def apply(self, state: BuilderState, name: str, value: str or None = None) -> str or None:
        if value:
            if os.path.exists(value):
                state.next_step += 2
            else:
                print_formatted_text(FormattedText([("class:error", f"Model not exist at {value}")]), style = state.shell_style)
        else:
            state.next_step += 1


class BuildParameterModelUrl:
    async def apply(self, state: BuilderState, name: str, value: str or None = None) -> str or None:
        if value is None:
            value = "1"
        
        url = value
        recommend = _recommend_model_urls.get(value)
        if recommend:
            url = recommend["url"]

        save_path = f"{AIStorage.get_instance().get_download_dir()}/{url.split('/').pop()}"

        print_formatted_text(FormattedText([("class:prompt", f"Will save the model to {save_path}:\n")]), style = state.shell_style)

        try:
            # get file size
            response = requests.head(url)
            file_size = int(response.headers.get('content-length', 0))

            # start download
            response = requests.get(url, stream=True)

            if response.status_code == 200:
                with open(save_path, 'wb') as f, ProgressBar() as pb:
                    for data in pb(response.iter_content(1024), total = (file_size + 1023) // 1024):
                        f.write(data)

                print_formatted_text(FormattedText([("class:prompt", f"Download model success, save at: {save_path}\n")]), style = state.shell_style)

                state.params["model_path"] = save_path
                state.next_step += 1
            else:
                print_formatted_text(FormattedText([("class:error", f"Download model failed, error: {response.status_code}\nYou can retry it or select another one.")]), style = state.shell_style)

        except Exception as e:
            print_formatted_text(FormattedText([("class:error", f"Download model failed: {e}\nYou can retry it or select another one.")]), style = state.shell_style)

class ParameterNodeNameApplier:
    async def apply(self, state: BuilderState, name: str, value: str or None = None) -> str or None:
        value = value or os.path.basename(state.params["model_path"])
        state.params["node_name"] = value
        state.next_step += 1

class ParameterPortApplier:
    async def apply(self, state: BuilderState, name: str, value: str or None = None) -> str or None:
        if value is None or value == "0":
            value = str(random.randint(10000, 60000))
            
        state.params["port"] = value
        state.next_step += 1

class ParameterNGpuLayersApplier:
    async def apply(self, state: BuilderState, name: str, value: str or None = None) -> str or None:
        value = value or "83"
        state.params["n_gpu_layers"] = value
        state.next_step += 1

class ParameterNCtxApplier:
    async def apply(self, state: BuilderState, name: str, value: str or None = None) -> str or None:
        value = value or "4096"
        state.params["n_ctx"] = value
        state.next_step += 1

class ParameterChatFormatApplier:
    async def apply(self, state: BuilderState, name: str, value: str or None = None) -> str or None:
        value = value or "llama-2"
        state.params["chat_format"] = value
        state.next_step += 1

class ParameterExternParamsApplier:
    async def apply(self, state: BuilderState, name: str, value: str or None = None) -> str or None:
        extern_params = value
        docker_image = ""
        gpu_options = []
        state.next_step += 1

        if state.params["n_gpu_layers"] == "0":
            docker_image = "ghcr.io/abetlen/llama-cpp-python:latest"
        else:
            gpu_options = ["--gpus", "all"]
            llama_cpp_python_repo_url = "https://github.com/abetlen/llama-cpp-python.git"
            download_path = AIStorage.get_instance().get_download_dir()
            llama_cpp_python_path = download_path + "/llama-cpp-python"

            # update the `llama-cpp-python`
            retry = True
            while retry:
                retry = False
                result = None
                if os.path.exists(llama_cpp_python_path):
                    result = subprocess.run(['git', 'pull'], cwd = llama_cpp_python_path, stdout = subprocess.PIPE, stderr = subprocess.PIPE, text = True)
                else:
                    result = subprocess.run(['git', 'clone', llama_cpp_python_repo_url, llama_cpp_python_path], stdout = subprocess.PIPE, stderr = subprocess.PIPE, text = True)

                if result.stderr:
                    print_formatted_text(FormattedText([("class:warn", result.stderr)]), style = state.shell_style)
                    while True:
                        sel = await state.prompt_session.prompt_async(f"Update 'llama-cpp-python' failed, you can press 'r' to retry, or 'c' to continue with the current version.", style = state.shell_style)
                        if sel == 'r':
                            retry = True
                            break
                        elif sel == 'c':
                            break
                        else:
                            pass # Select again
                else:
                    break
            
            # build the image
            docker_image = 'llama-cpp-python-cuda'
            retry = True
            while retry:
                retry = False
                result = subprocess.run(['docker', 'rmi', docker_image], stdout = subprocess.PIPE, stderr = subprocess.PIPE, text = True)
                result = subprocess.run(['docker', 'build', '-t', docker_image, f"{llama_cpp_python_path}/docker/cuda_simple/"], stdout = subprocess.PIPE, stderr = subprocess.PIPE, text = True)

                if result.stderr:
                    print_formatted_text(FormattedText([("class:warn", result.stderr)]), style = state.shell_style)
                    while True:
                        sel = await state.prompt_session.prompt_async(f"Build the image failed, you can press 'r' to retry, or 'c' to continue with the current version.", style = state.shell_style)
                        if sel == 'r':
                            retry = True
                            break
                        elif sel == 'c':
                            break
                        else:
                            pass # Select again
                else:
                    break
            
        retry = True
        while retry:
            retry = False
            run_options = ['docker', 'run', '-d']

            if gpu_options:
                run_options.extend(gpu_options)
            
            run_options.extend([
                '-p', f"{state.params['port']}:8000",
                '-v', f"{os.path.dirname(state.params['model_path'])}:/models", '-e', f"MODEL=/models/{os.path.basename(state.params['model_path'])}",
                'llama-cpp-python-cuda',
                'python3', '-m', 'llama_cpp.server',
                '--n_gpu_layers', state.params["n_gpu_layers"],
                '--n_ctx', state.params["n_ctx"],
                '--chat_format', state.params["chat_format"],
                ])
            
            if extern_params:
                run_options.extend(extern_params.split(' '))

            print_formatted_text(FormattedText([("class:prompt", f"Will start service with: {' '.join(run_options)}")]), style = state.shell_style)

            result = subprocess.run(run_options, stdout = subprocess.PIPE, stderr = subprocess.PIPE, text = True)

            if result.stderr:
                print_formatted_text(FormattedText([("class:warn", result.stderr)]), style = state.shell_style)
                while True:
                    sel = await state.prompt_session.prompt_async(f"Start the node service failed, you can press 'r' to retry, or 'a' to abort.", style = state.shell_style)
                    if sel == 'r':
                        retry = True
                        break
                    elif sel == 'a':
                        break
                    else:
                        pass # Select again
            else:
                local_url = f'http://localhost:{state.params["port"]}'
                foreign_url = 'http://{your-host-address}:' + state.params["port"]
                model_name = state.params['node_name']

                ComputeNodeConfig.get_instance().add_node("llama", local_url, model_name)
                ComputeNodeConfig.get_instance().save()
                node = LocalLlama_ComputeNode(local_url, model_name)
                node.start()
                ComputeKernel.get_instance().add_compute_node(node)

                print_formatted_text(FormattedText([(
                    "class:prompt",
f"""
Congratulations! The node ({model_name}) service successed.
You can access it with follow url:
{local_url}
And 'http://{foreign_url}' in other computers.
Now you can refer it in agents as `llm_model_name={model_name}`
"""
                )]), style = state.shell_style)
                break

_recommend_model_urls = {
    "1": {
        "model": "Llama-2-70B-Chat-GGUF",
        "url": "https://huggingface.co/TheBloke/Llama-2-70B-chat-GGUF/resolve/main/llama-2-70b-chat.Q4_0.gguf"
    },
    "2": {
        "model": "Llama-2-13B-Chat-GGUF",
        "url": "https://huggingface.co/TheBloke/Llama-2-13B-chat-GGUF/resolve/main/llama-2-13b-chat.Q4_0.gguf"
    },
    "3": {
        "model": "Llama-2-7B-Chat-GGUF",
        "url": "https://huggingface.co/TheBloke/Llama-2-7B-Chat-GGUF/resolve/main/llama-2-7b-chat.Q4_K_M.gguf"
    },
}

_recommend_model_url_table_str = ""
for i in range(1, 999):
    id = str(i)
    info = _recommend_model_urls.get(id)
    if info:
        _recommend_model_url_table_str += f"\n\t{id}\t{info['model']}\t{info['url']}"
    else:
        break

_params = [
    BuildParameter("model_path", BuildParameterModelPath(), "Please input the model file path (Press 'Enter' if you need to download it)"),
    BuildParameter("model_url", BuildParameterModelUrl(), "Please input (default: Llama-2-70B-chat)", f"Now you need input the url to download the model, or you can input the 'ID' in the follow table to select one:\n\tID\tmodel\t\turl{_recommend_model_url_table_str}"),
    BuildParameter("node_name", ParameterNodeNameApplier(), "Please input name for your node, and you can set it in 'llm_model_name' of 'agent.toml' (default: the name of the model file)"),
    BuildParameter("port", ParameterPortApplier(), "Please input the port which the node server will listen on (default: random)"),
    BuildParameter("n_gpu_layers", ParameterNGpuLayersApplier(), "Please input layers offload to GPU (<=83 for Llama, 0 for CPU only, default: 83)"),
    BuildParameter("n_ctx", ParameterNCtxApplier(), "Please input the content limit (default: 4096)"),
    BuildParameter("chat_format", ParameterChatFormatApplier(), "Please input the chat format (default: llama-2)"),
    BuildParameter("extern_params", ParameterExternParamsApplier(), "Please input other parameters refer to 'llama-cpp-python'(https://github.com/abetlen/llama-cpp-python), press 'Enter' to ignore it"),
]

class LocalLlamaNodeBuilder(LocalComputeNodeBuilder):
    def next_parameter(self) -> BuildParameter or None:
        if self.state.next_step < len(_params):
            return _params[self.state.next_step]
