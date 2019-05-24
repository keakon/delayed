# -*- coding: utf-8 -*-

import os

from delayed.task import Task
from delayed.worker import Worker

from .common import CONN, DELAY, QUEUE, QUEUE_NAME


TEST_STRING = 'test'
ERROR_STRING = 'error'


def error_func():
    raise Exception('test error')


class TestWorker(object):
    def test_run(self):
        def success_handler(task):
            worker.stop()

        def error_handler(task, exit_status, error):
            os.write(w, ERROR_STRING)
            worker.stop()

        CONN.delete(QUEUE_NAME)
        r, w = os.pipe()
        task = Task.create(os.write, (w, TEST_STRING))
        QUEUE.enqueue(task)
        worker = Worker(QUEUE, success_handler=success_handler, error_handler=error_handler)
        worker.run()
        assert os.read(r, 4) == TEST_STRING

        task = Task.create(error_func)
        QUEUE.enqueue(task)
        worker.run()
        assert os.read(r, 5) == ERROR_STRING

        DELAY(os.write)(w, TEST_STRING)
        worker.run()
        assert os.read(r, 4) == TEST_STRING
        os.close(r)
        os.close(w)
        worker = None
