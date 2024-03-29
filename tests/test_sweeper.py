# -*- coding: utf-8 -*-

import threading
import time

from delayed.queue import Queue, _NOTI_KEY_SUFFIX
from delayed.sweeper import Sweeper
from delayed.task import PyTask
from pytest import fail

from .common import CONN, func, QUEUE, QUEUE_NAME, NOTI_KEY


class TestSweeper:
    def test_run(self):
        queue_name = 'test'
        noti_key = queue_name + _NOTI_KEY_SUFFIX
        CONN.delete(QUEUE_NAME, NOTI_KEY, queue_name, noti_key)

        queue = Queue('test', CONN, 0.01)
        queue._worker_id = 123
        sweeper = Sweeper([QUEUE, queue], 0.05)

        task = PyTask(func, (1, 2))
        QUEUE.enqueue(task)
        CONN.lpop(NOTI_KEY)

        task = QUEUE.dequeue()
        assert task is None

        thread = threading.Thread(target=sweeper.run)
        thread.start()

        try:
            time.sleep(0.1)
            task = QUEUE.dequeue()
            assert task is not None
            QUEUE.release()

            task2 = PyTask(func, (1, 2))
            queue.enqueue(task2)
            CONN.lpop(noti_key)

            for _ in range(10):  # retry for slow machines
                time.sleep(0.1)
                task2 = queue.dequeue()
                if task2 is not None:
                    break
            else:
                fail('task2 is None')

            queue.release()
        finally:
            sweeper.stop()
            thread.join()
