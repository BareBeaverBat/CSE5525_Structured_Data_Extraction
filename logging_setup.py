import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from logging import Logger, StreamHandler

fmtr = logging.Formatter("%(asctime)s;%(name)s;%(levelname)s:%(message)s")
console_handler = StreamHandler(sys.stdout)
console_handler.setFormatter(fmtr)
console_handler.setLevel(logging.INFO)
file_handler = TimedRotatingFileHandler("structured_data_extraction_experiments.log", when="D", backupCount=14, encoding="utf-8")
file_handler.setFormatter(fmtr)
file_handler.setLevel(logging.DEBUG)


def create_logger(lgr_nm: str) -> Logger:
    new_logger = logging.getLogger(lgr_nm)
    new_logger.setLevel(logging.DEBUG)
    new_logger.addHandler(console_handler)
    new_logger.addHandler(file_handler)
    return new_logger
