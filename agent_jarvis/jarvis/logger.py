import logging

from jarvis import CFG


def _init_logger():
    pass


_init_logger()

logger = logging.getLogger("main_logger")
logger.setLevel(CFG.log_level)

file_handler = logging.FileHandler('log.txt')
console_handler = logging.StreamHandler()

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)
