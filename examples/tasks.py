# -*- coding: utf-8 -*-

import os
import time

from delayed.delay import delayed
from delayed.logger import logger, setup_logger

from .client import queue


setup_logger()

DELAYED = delayed(queue)
i = 0

def func1(*args, **kwargs):
    logger.info(os.getpid())
    time.sleep(1)


@DELAYED
def func2(*args, **kwargs):
    logger.info(os.getpid())
    time.sleep(1)

@DELAYED(retry=3)
def func3():
    global i
    i += 1
    if i % 2:
        raise Exception('error')
