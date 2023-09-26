
import sys
import os
import logging
import socket
import socks
import logging

directory = os.path.dirname(__file__)
sys.path.append(directory + '/../../')

from aios_kernel import AIStorage

logger = logging.getLogger(__name__)

def apply_storage():
    proxy_cfg = AIStorage.get_instance().get_user_config().get_config_item("proxy")
    if proxy_cfg is None:
        return
    
    host_url = proxy_cfg.value
    if host_url is not None and len(host_url) > 3:
        url_fields = host_url.split("@")
        proxy_type, host, username, password = url_fields[0], None, None, None
        if len(url_fields) > 1:
            host = url_fields[1]
            if len(url_fields) > 2:
                username = url_fields[2]
                if len(url_fields) > 3:
                    password = url_fields[3]
        
        match proxy_type:
            case "socks5":
                (host, port) = host.split(":")
                socks.set_default_proxy(socks.SOCKS5, host, int(port), username = username, password = password)
                socket.socket = socks.socksocket
                logger.info(f"proxy {host_url} will be used.")
            case _:
                logger.error(f"the proxy type ({proxy_type}) has not support. proxy will not be used.")
                

def declare_user_config():
    user_config = AIStorage.get_instance().get_user_config()
    user_config.add_user_config("proxy", "set your proxy service as 'proxy_type@host:port@username@password', 'proxy_type' = 'socks5'", True, None)
