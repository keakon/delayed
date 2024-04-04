# -*- coding: utf-8 -*-

import os
import signal

import redis

from delayed.delay import delayed
from delayed.queue import Queue, _PROCESSING_KEY_SUFFIX, _NOTI_KEY_SUFFIX
from delayed.worker import Worker


QUEUE_NAME = 'default'
NOTI_KEY = QUEUE_NAME + _NOTI_KEY_SUFFIX
PROCESSING_KEY = QUEUE_NAME + _PROCESSING_KEY_SUFFIX

CONN = redis.Redis()
QUEUE = Queue(QUEUE_NAME, CONN, 0.01)
WORKER = Worker(QUEUE)
DELAYED = delayed(QUEUE)

WORKER.generate_id()

i = 0


def func(a, b):
    return a + b


def func2():
    return


def func3():
    global i
    i += 1
    if i % 5 == 0:
        os.kill(os.getpid(), signal.SIGHUP)
    else:
        raise Exception('error')
