import daemon
from time import sleep
import logging

logger = logging.getLogger(__name__)

logging.basicConfig(filename="daemon_test.log",filemode="w",encoding='utf-8',force=True,
                    level=logging.INFO,
                    format='[%(asctime)s]%(name)s[%(levelname)s]: %(message)s')

def main_program():
    while True:
        logger.info("hello world")
        sleep(1)

with daemon.DaemonContext():
    main_program()
