# -*- coding: utf-8 -*-

import os
import signal

from delayed.task import PyTask
from delayed.queue import Queue
from delayed.worker import Worker

from .common import CONN, func3, NOTI_KEY, PROCESSING_KEY, QUEUE, QUEUE_NAME, WORKER


def stop(pid: int):
    os.kill(pid, signal.SIGHUP)


class TestWorker:
    def test_generate_id(self):
        QUEUE.go_offline()  # make sure no worker ids are used

        queue1 = Queue(QUEUE_NAME, conn=CONN)
        worker1 = Worker(queue1, id_bits=1)
        worker1.generate_id()
        assert worker1._id is not None
        assert 0 <= worker1._id < 2

        queue2 = Queue(QUEUE_NAME, conn=CONN)
        worker2 = Worker(queue2, id_bits=1)
        worker2.generate_id()
        assert worker2._id is not None
        assert 0 <= worker2._id < 2
        assert worker1._id != worker2._id

        queue1.go_offline()
        queue2.go_offline()

    def test_run(self):
        CONN.delete(QUEUE_NAME, NOTI_KEY, PROCESSING_KEY)

        task = PyTask(func3)
        QUEUE.enqueue(task)

        task = PyTask(stop, (os.getpid(),))
        QUEUE.enqueue(task)

        WORKER.run()

        CONN.delete(QUEUE_NAME, NOTI_KEY, PROCESSING_KEY)
