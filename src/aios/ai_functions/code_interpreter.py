# pylint:disable=E0402
import logging
import os
import pathlib
import shutil
import subprocess
import sys
import re
import time
import ast
from concurrent.futures import ThreadPoolExecutor
from hashlib import md5
from typing import Optional, Union, List, Tuple
from generic_escape import GenericEscape

from ..storage.storage import AIStorage

try:
    import docker
except ImportError:
    docker = None

CODE_BLOCK_PATTERN = r"```[ \t]*(\w+)?[ \t]*\r?\n(.*?)\r?\n[ \t]*```"
UNKNOWN = "unknown"
TIMEOUT_MSG = "Timeout"
DEFAULT_TIMEOUT = 600
WIN32 = sys.platform == "win32"
PATH_SEPARATOR = WIN32 and "\\" or "/"

logger = logging.getLogger(__name__)


BUILT_IN_MODULES = set(
    [
        "sys",
        "os",
        "math",
        "random",
        "datetime",
        "json",
        "re",
        "subprocess",
        "time",
        "threading",
        "logging",
        "collections",
        "itertools",
        "functools",
        "operator",
        "pathlib",
        "shutil",
        "tempfile",
        "pickle",
        "io",
        "argparse",
        "typing",
        "unittest",
        "contextlib",
        "abc",
        "heapq",
        "bisect",
        "copy",
        "decimal",
        "fractions",
        "hashlib",
        "secrets",
        "statistics",
        "difflib",
        "doctest",
        "enum",
        "inspect",
        "traceback",
        "weakref",
        "gc",
        "mmap",
        "msvcrt",
        "winreg",
        "array",
        "audioop",
        "binascii",
        "cProfile",
        "concurrent.futures",
        "configparser",
        "csv",
        "ctypes",
        "dateutil",
        "dis",
        "fnmatch",
        "getopt",
        "glob",
        "gzip",
        "pdb",
        "pprint",
        "profile",
        "pstats",
        "queue",
        "socket",
        "sqlite3",
        "ssl",
        "struct",
        "tarfile",
        "telnetlib",
        "timeit",
        "tokenize",
        "uuid",
        "xml",
        "zipfile",
        "zlib",
    ]
)


def get_imports(code: str) -> List[str]:
    root = ast.parse(code)

    imports = []
    for node in ast.iter_child_nodes(root):
        if isinstance(node, ast.Import):
            module_names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            module_names = [node.module]
        else:
            continue

        for name in module_names:
            # Exclude built-in modules
            if name not in BUILT_IN_MODULES:
                imports.append(name)

    return imports


def write_requirements(code: str, requirements_filepath: str):
    imports = get_imports(code)

    with open(requirements_filepath, "w") as file:
        for module in imports:
            file.write(module + "\n")


def _cmd(lang):
    if lang.startswith("python") or lang in ["bash", "sh", "powershell"]:
        return lang
    if lang in ["shell"]:
        return "sh"
    if lang in ["ps1"]:
        return "powershell"
    raise NotImplementedError(f"{lang} not recognized in code execution")


def create_runner(code: str, timeout: int = 30) -> str:
    """
    Create a Python script that runs the code and prints the output
    """
    code = GenericEscape().escape(code)
    # Create a runner script
    runner = f"""
import os
import subprocess

my_env = os.environ.copy()
my_env["PYTHONIOENCODING"] = "utf-8"

process = subprocess.Popen(
    f"python -i -q -u".split(),
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=0,
    universal_newlines=True,
    env=my_env
)

process.stdin.write("{code}" + "\\n")
process.stdin.write("exit()\\n")
process.stdin.flush()

try:
    process.wait({timeout})
except Exception as e:
    process.terminate()

for line in iter(process.stdout.readline, ""):
    print(line)
    
for line in iter(process.stderr.readline, ""):
    if line.startswith(">>>"):
        continue
    print(line)
"""
    return runner


def _run_cmd(cmd: [str], work_dir: str, timeout: int) -> str:
    if WIN32:
        logger.warning("SIGALRM is not supported on Windows. No timeout will be enforced.")
        result = subprocess.run(
            cmd,
            cwd=work_dir,
            capture_output=True,
            text=True,
        )
    else:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                subprocess.run,
                cmd,
                cwd=work_dir,
                capture_output=True,
                text=True,
            )
            result = future.result(timeout=timeout)
    return result


def execute_code(
        code: Optional[str] = None,
        timeout: Optional[int] = None,
        filename: Optional[str] = None,
        work_dir: Optional[str] = None,
        use_docker: Optional[Union[List[str], str, bool]] = None,
        lang: Optional[str] = "python",
) -> Tuple[int, str]:
    """Execute code in a docker container.
    This function is not tested on MacOS.

    Args:
        code (Optional, str): The code to execute.
            If None, the code from the file specified by filename will be executed.
            Either code or filename must be provided.
        timeout (Optional, int): The maximum execution time in seconds.
            If None, a default timeout will be used. The default timeout is 600 seconds. On Windows, the timeout is not enforced when use_docker=False.
        filename (Optional, str): The file name to save the code or where the code is stored when `code` is None.
            If None, a file with a randomly generated name will be created.
            The randomly generated file will be deleted after execution.
            The file name must be a relative path. Relative paths are relative to the working directory.
        work_dir (Optional, str): The working directory for the code execution.
            If None, a default working directory will be used.
            The default working directory is the "extensions" directory under
            "path_to_autogen".
        use_docker (Optional, list, str or bool): The docker image to use for code execution.
            If a list or a str of image name(s) is provided, the code will be executed in a docker container
            with the first image successfully pulled.
            If None, False or empty, the code will be executed in the current environment.
            Default is None, which will be converted into an empty list when docker package is available.
            Expected behaviour:
                - If `use_docker` is explicitly set to True and the docker package is available, the code will run in a Docker container.
                - If `use_docker` is explicitly set to True but the Docker package is missing, an error will be raised.
                - If `use_docker` is not set (i.e., left default to None) and the Docker package is not available, a warning will be displayed, but the code will run natively.
            If the code is executed in the current environment,
            the code must be trusted.
        lang (Optional, str): The language of the code. Default is "python".

    Returns:
        int: 0 if the code executes successfully.
        str: The error message if the code fails to execute; the stdout otherwise.
    """
    if all((code is None, filename is None)):
        error_msg = f"Either {code=} or {filename=} must be provided."
        logger.error(error_msg)
        raise AssertionError(error_msg)

    # Warn if use_docker was unspecified (or None), and cannot be provided (the default).
    # In this case the current behavior is to fall back to run natively, but this behavior
    # is subject to change.
    if use_docker is None:
        if docker is None:
            use_docker = False
            logger.warning(
                "execute_code was called without specifying a value for use_docker. Since the python docker package is not available, code will be run natively. Note: this fallback behavior is subject to change"
            )
        else:
            # Default to true
            use_docker = True

    timeout = timeout or DEFAULT_TIMEOUT
    original_filename = filename
    if WIN32 and lang in ["sh", "shell"] and (not use_docker):
        lang = "ps1"
    if filename is None:
        code_hash = md5(code.encode()).hexdigest()
        # create a file with a automatically generated name
        filename = f"tmp_code_{code_hash}.{'py' if lang.startswith('python') else lang}"
    if work_dir is None:
        WORKING_DIR = os.path.join(AIStorage.get_instance().get_myai_dir(), "tmp_code")
        pathlib.Path(WORKING_DIR).mkdir(exist_ok=True)
        work_dir = os.path.join(WORKING_DIR, code_hash)
        pathlib.Path(work_dir).mkdir(exist_ok=True)
    filepath = os.path.join(work_dir, filename)
    file_dir = os.path.dirname(filepath)
    os.makedirs(file_dir, exist_ok=True)
    if code is not None:
        write_requirements(code, os.path.join(file_dir, "requirements.txt"))
        code = create_runner(code, 30)
        with open(filepath, "w", encoding="utf-8") as fout:
            fout.write(code)


    # check if already running in a docker container
    in_docker_container = os.path.exists("/.dockerenv")
    if not use_docker or in_docker_container:
        try:
            env_cmd = ["python", "-m", "venv", os.path.join(file_dir, "venv")]
            _run_cmd(env_cmd, file_dir, timeout)
            if WIN32:
                venv_path = os.path.join(file_dir, "venv", "Scripts")
            else:
                venv_path = os.path.join(file_dir, "venv", "bin")
            pip_cmd = [os.path.join(venv_path, "python"), "-m", "pip", "install", "-r", "requirements.txt"]
            _run_cmd(pip_cmd, file_dir, timeout)
            # already running in a docker container
            cmd = [
                os.path.join(venv_path, "python"),
                f".\\{filename}" if WIN32 else filename,
            ]
            result = _run_cmd(cmd, file_dir, timeout)
        except TimeoutError:
            if original_filename is None:
                shutil.rmtree(os.path.join(file_dir, "venv"))
                os.remove(filepath)
                os.remove(os.path.join(file_dir, "requirements.txt"))
                try:
                    os.removedirs(file_dir)
                except Exception:
                    pass
            return 1, TIMEOUT_MSG
        if original_filename is None:
            shutil.rmtree(os.path.join(file_dir, "venv"))
            os.remove(filepath)
            os.remove(os.path.join(file_dir, "requirements.txt"))
            try:
                os.removedirs(file_dir)
            except Exception:
                pass
        if result.returncode:
            logs = result.stderr
            if original_filename is None:
                abs_path = str(pathlib.Path(filepath).absolute())
                logs = logs.replace(str(abs_path), "").replace(filename, "")
            else:
                abs_path = str(pathlib.Path(work_dir).absolute()) + PATH_SEPARATOR
                logs = logs.replace(str(abs_path), "")
        else:
            logs = result.stdout
        return result.returncode, logs

    # create a docker client
    client = docker.from_env()
    image_list = (
        ["python:3-alpine", "python:3", "python:3-windowsservercore"]
        if use_docker is True
        else [use_docker]
        if isinstance(use_docker, str)
        else use_docker
    )
    for image in image_list:
        # check if the image exists
        try:
            client.images.get(image)
            break
        except docker.errors.ImageNotFound:
            # pull the image
            logger.info("Pulling image", image)
            try:
                client.images.pull(image, stream=True, decode=True)
                break
            except docker.errors.DockerException as e:
                logger.error("Failed to pull image", image)
                logger.exception(e)
    # get a randomized str based on current time to wrap the exit code
    exit_code_str = f"exitcode{time.time()}"
    start_str = f'start{time.time()}'
    abs_path = pathlib.Path(work_dir).absolute()
    cmd = [
        "sh",
        "-c",
        f"pip install --quiet -r requirements.txt; echo -n {start_str}; {_cmd(lang)} {filename}; exit_code=$?; echo -n {exit_code_str}; echo -n $exit_code; echo {exit_code_str};",
    ]
    # create a docker container
    container = client.containers.run(
        image,
        command=cmd,
        working_dir="/workspace",
        detach=True,
        # get absolute path to the working directory
        volumes={abs_path: {"bind": "/workspace", "mode": "rw"}},
    )
    start_time = time.time()
    while container.status != "exited" and time.time() - start_time < timeout:
        # Reload the container object
        container.reload()
    if container.status != "exited":
        container.stop()
        container.remove()
        if original_filename is None:
            os.remove(filepath)
        return 1, TIMEOUT_MSG, image
    # get the container logs
    logs: str = container.logs().decode("utf-8").rstrip()
    start_pos = logs.find(start_str)
    if start_pos != -1:
        logs = logs[start_pos + len(start_str):]
    # # commit the image
    # tag = filename.replace("/", "")
    # container.commit(repository="python", tag=tag)
    # remove the container
    container.remove()
    # check if the code executed successfully
    exit_code = container.attrs["State"]["ExitCode"]
    if exit_code == 0:
        # extract the exit code from the logs
        pattern = re.compile(f"{exit_code_str}(\\d+){exit_code_str}")
        match = pattern.search(logs)
        exit_code = 1 if match is None else int(match.group(1))
        # remove the exit code from the logs
        logs = logs if match is None else pattern.sub("", logs)

    if original_filename is None:
        os.remove(filepath)
        os.remove(os.path.join(file_dir, "requirements.txt"))
        os.removedirs(file_dir)
    if exit_code:
        logs = logs.replace(f"/workspace/{filename if original_filename is None else ''}", "")
    # return the exit code, logs and image
    return exit_code, logs

class CodeInterpreterFunction(AIFunction):
    def __init__(self):
        self.func_id = "system.code_interpreter"
        self.description = "execute python code"
        self.parameters = ParameterDefine.create_parameters({
            "code": {"type": "string", "description": "python code"}
        })

    def get_name(self) -> str:
        return self.func_id

    def get_description(self) -> str:
        return self.description

    def get_parameters(self) -> Dict:
        return self.parameters

    async def execute(self, **kwargs) -> str:
        code = kwargs.get("code")
        ret_code, result = execute_code(code=code)
        if ret_code == 0:
            return result.strip()
        else:
            return result.strip()

    def is_local(self) -> bool:
        return True

    def is_in_zone(self) -> bool:
        return True

    def is_ready_only(self) -> bool:
        return False
