
import sys
import os
import logging
import socket
import socks

directory = os.path.dirname(__file__)
sys.path.append(directory + '/../../')

from aios_kernel import AIStorage

def apply_storage():
    proxy_cfg = AIStorage.get_instance().get_user_config().get_user_config("proxy")
    if proxy_cfg is None:
        return
    
    host_url = proxy_cfg.value
    if host_url is not None:
        (proxy_type, host) = host_url.split("@")
        match proxy_type:
            case "socks5":
                (host, port) = host.split(":")
                socks.set_default_proxy(socks.SOCKS5, host, int(port))
                socket.socket = socks.socksocket
                print("proxy {host_url} will be used.")
            case _:
                print("the proxy type ({proxy_type}) has not support.")

def declare_user_config():
    user_config = AIStorage.get_instance().get_user_config()
    user_config.add_user_config("proxy", "set your proxy service as 'proxy_type@host:port', 'proxy_type' = 'socks5'", True, None)
