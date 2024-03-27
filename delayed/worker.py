# -*- coding: utf-8 -*-

import binascii
import os
import signal
import sys
import threading
import time
import traceback
from typing import Union

from .constants import DEFAULT_SLEEP_TIME, MAX_SLEEP_TIME, Status
from .keep_alive import KeepAliveThread
from .logger import logger
from .queue import Queue
from .task import PyTask

class Worker:
    """Worker is the class of Python task worker.

    Args:
        queue (delayed.queue.Queue): The task queue of the worker.
        keep_alive_interval (int or float): The worker marks itself as alive for every `keep_alive_interval` seconds.
    """

    def __init__(self, queue: Queue, keep_alive_interval: Union[int, float] = 15):
        queue._worker_id = self._id = binascii.hexlify(os.urandom(16))
        self._queue = queue
        self._keep_alive_interval = keep_alive_interval
        self._status = Status.STOPPED
        self._cond = threading.Condition()

    def run(self):  # pragma: no cover
        """Runs the worker."""
        logger.debug('Starting worker %s.', self._id)
        self._status = Status.RUNNING
        self._register_signals()

        thread = KeepAliveThread(self)
        thread.start()

        try:
            sleep_time = DEFAULT_SLEEP_TIME
            while self._status == Status.RUNNING:
                try:
                    task = self._queue.dequeue()
                except Exception:  # pragma: no cover
                    logger.exception('Failed to dequeue task.')
                    time.sleep(sleep_time)
                    sleep_time *= 2
                    if sleep_time > MAX_SLEEP_TIME:
                        sleep_time = MAX_SLEEP_TIME
                else:
                    sleep_time = DEFAULT_SLEEP_TIME
                    if task:
                        try:
                            task.execute()
                        except Exception:
                            logger.exception('Failed to execute task %s.', task._func_path)

                            _, _, exc_traceback = sys.exc_info()
                            if len(traceback.format_tb(exc_traceback)) > 2:
                                self._requeue_task(task)
                            else:
                                # invalid call, should not be retried
                                self._release_task()
                        else:
                            self._release_task()
        finally:
            self._unregister_signals()
            self._status = Status.STOPPED
            with self._cond:
                self._cond.notify()
            thread.join()
            logger.debug('Stopped worker %s.', self._id)

    def stop(self):
        """Stops the worker."""
        if self._status == Status.RUNNING:
            logger.debug('Stopping worker %s.', self._id)
            self._status = Status.STOPPING

    def _requeue_task(self, task: PyTask):
        """Requeues a dequeued task.

        Args:
            task (delayed.task.PyTask): The task to be requeued.
        """
        logger.debug('Requeuing task %s', task._func_path)
        try:
            self._queue.enqueue(task)
        except Exception:
            logger.exception('Failed to requeue task %s', task._func_path)

    def _release_task(self):
        """Releases the currently dequeued task."""
        try:
            self._queue.release()
        except Exception:  # pragma: no cover
            logger.exception('Failed to release task of worker %s.', self._id)

    def _register_signals(self):
        """Registers signal handlers."""
        def stop(signum, frame):
            logger.debug('Received SIGHUP.')
            self.stop()
        signal.signal(signal.SIGHUP, stop)

    def _unregister_signals(self):
        """Unregisters signal handlers."""
        signal.signal(signal.SIGHUP, signal.SIG_DFL)
