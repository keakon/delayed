# -*- coding: utf-8 -*-

import errno
import gc
from io import BytesIO
import os
import select
import signal
import struct
import sys
import time

from .logger import logger
from .status import Status
from .task import Task
from .utils import drain_out, ignore_signal, non_blocking_pipe, read1, read_all, read_bytes, try_write, write_byte


_SIGNAL_MASK = 0xff
_PIPE_SIZE = 65536


class Worker(object):
    """Worker is the abstract class of task worker.

    Args:
        queue (delayed.queue.Queue): The task queue of the worker.
        kill_timeout (int or float): The kill timeout in seconds of the worker.
            If a task runs out of time, the monitor will send SIGTERM signal to the worker.
            If the worker not exited in `kill_timeout` seconds, the monitor will send SIGKILL
            signal then.
        success_handler (callable): The success callback.
        error_handler (callable): The error callback.
    """

    __slots__ = ['_queue', '_kill_timeout', '_success_handler', '_error_handler', '_status']

    def __init__(self, queue, kill_timeout=5, success_handler=None, error_handler=None):
        self._queue = queue
        self._kill_timeout = kill_timeout
        self._success_handler = success_handler
        self._error_handler = error_handler
        self._status = Status.STOPPED

    def run(self):  # pragma: no cover
        """Runs the worker."""
        raise NotImplementedError

    def stop(self):
        """Stops the worker."""
        self._status = Status.STOPPING
        logger.debug('Stopping %s %d.', self.__class__.__name__, os.getpid())

    def _handler_success(self, task):
        """Calls the success handler.

        Args:
            task (delayed.task.Task): The success task.
        """
        logger.debug('Calling success handle for task %d.', task.id)
        try:
            self._success_handler(task)
        except Exception:  # pragma: no cover
            logger.exception('Call success handler for task %d failed.', task.id)
        else:
            logger.debug('Called success handle for task %d.', task.id)

    def _handle_error(self, task, exit_status, exc_info):
        """Calls the error handler.

        Args:
            task (delayed.task.Task): The error task.
            exit_status (int or None): The exit status of the worker.
            exc_info (type, Exception, traceback.Traceback): The exc_info if the worker raises an
                uncaught exception.
        """
        logger.debug('Calling error handle for task %d.', task.id)
        try:
            self._error_handler(task, exit_status, exc_info)
        except Exception:  # pragma: no cover
            logger.exception('Call error handle for task %d failed.', task.id)
        else:
            logger.debug('Called error handle for task %d.', task.id)

    def _requeue_task(self, task):
        """Requeues a task.

        Args:
            task (delayed.task.Task): The task to be requeued.
        """
        try:
            self._queue.requeue(task)
        except Exception:  # pragma: no cover
            logger.exception('Requeue task %d failed.', task.id)

    def _release_task(self, task):
        """Releases a task.
        A task can be released twice by both the monitor and the worker.

        Args:
            task (delayed.task.Task): The task to be released.
        """
        try:
            self._queue.release(task)
        except Exception:  # pragma: no cover
            logger.exception('Release task %d failed.', task.id)

    def _register_signals(self):
        """Registers signal handlers."""
        def stop(signum, frame):
            self.stop()
            logger.debug('Received SIGHUP.')
        signal.signal(signal.SIGHUP, stop)

    def _unregister_signals(self):
        """Unregisters signal handlers."""
        signal.signal(signal.SIGHUP, signal.SIG_DFL)


class ForkedWorker(Worker):
    """ForkedWorker forks a worker process for each task."""

    __slots__ = ['_waker', '_child_pid']

    def run(self):
        logger.debug('Starting ForkedWorker %d.', os.getpid())
        self._status = Status.RUNNING
        self._register_signals()

        try:
            while self._status == Status.RUNNING:
                try:
                    task = self._queue.dequeue()
                except Exception:  # pragma: no cover
                    logger.exception('Dequeue task failed.')
                else:
                    if task:
                        gc.disable()  # https://bugs.python.org/issue1336
                        try:
                            pid = os.fork()
                        except OSError:  # pragma: no cover
                            gc.enable()
                            logger.exception('Fork task worker failed.')
                        else:
                            gc.enable()
                            if pid == 0:  # child
                                self._run_task(task)  # pragma: no cover
                            else:  # parent
                                logger.debug('Forked a child worker %d.', pid)
                                self._child_pid = pid
                                self._monitor_task(task, pid)
                                self._child_pid = None
        finally:
            self._unregister_signals()
            self._status = Status.STOPPED
            logger.debug('Stopped ForkedWorker %d.', os.getpid())

    def _register_signals(self):
        super(ForkedWorker, self)._register_signals()
        signal.signal(signal.SIGCHLD, ignore_signal)

        self._waker = r, w = non_blocking_pipe()
        signal.set_wakeup_fd(w)
        self._child_pid = None

    def _unregister_signals(self):
        signal.set_wakeup_fd(-1)
        os.close(self._waker[0])
        os.close(self._waker[1])
        del self._waker

        signal.signal(signal.SIGCHLD, signal.SIG_DFL)
        super(ForkedWorker, self)._unregister_signals()

    def _monitor_task(self, task, pid):
        """Monitors the task.

        Args:
            task (delayed.task.Task): The task to be monitored.
            pid (int): The worker's pid.
        """
        now = time.time()
        if task.timeout:
            deadline = now + task.timeout / 1000
        else:
            deadline = now + self._queue.default_timeout / 1000
        kill_deadline = deadline + self._kill_timeout
        r = self._waker[0]
        rlist = (r,)
        killing = False
        try:
            while True:
                try:
                    if select.select(rlist, (), (), 0.1):
                        drain_out(r)
                        p, exit_status = os.waitpid(pid, os.WNOHANG)
                        if p != 0:
                            if exit_status:
                                kill_signal = exit_status & _SIGNAL_MASK
                                if kill_signal:
                                    if self._error_handler:
                                        self._handle_error(task, kill_signal, None)
                                else:  # task hasn't been run
                                    self._requeue_task(task)
                                    return
                            break
                except OSError as e:  # pragma: no cover
                    if e.errno != errno.EINTR:
                        raise
                except select.error as e:  # pragma: no cover
                    if e.args[0] != errno.EINTR:
                        raise

                now = time.time()
                if now >= deadline:
                    if now >= kill_deadline:
                        os.kill(pid, signal.SIGKILL)
                    elif not killing:
                        os.kill(pid, signal.SIGTERM)
                        killing = True
        except Exception:  # pragma: no cover
            logger.exception('Monitor task %d error.', task.id)
            if self._error_handler:
                self._error_handler(task, None, sys.exc_info())

        self._release_task(task)

    def _run_task(self, task):
        """Runs a task.

        Args:
            task (delayed.task.Task): The task to be run.
        """
        error_code = 1
        try:
            self._unregister_signals()
            error_code = 0
            try:
                task.run()
            except Exception:
                logger.exception('Run task %d failed.', task.id)
                if self._error_handler:
                    self._error_handler(task, None, sys.exc_info())
            else:
                if self._success_handler:
                    self._handler_success(task)
            finally:
                self._release_task(task)
        finally:
            os._exit(error_code)


class PreforkedWorker(Worker):
    """PreforkedWorker forks a worker process and reuses it for each task.
    If a task runs out of time, the forked worker process will be killed by the monitor, then a new
    worker process will be forked for subsequent tasks.
    """

    __slots__ = ['_waker', '_task_channel', '_result_channel', '_child_pid']

    def run(self):
        logger.debug('Starting PreforkedWorker %d.', os.getpid())
        self._status = Status.RUNNING
        self._register_signals()

        try:
            while self._status == Status.RUNNING:
                try:
                    task = self._queue.dequeue()
                except Exception:  # pragma: no cover
                    logger.exception('Dequeue task failed.')
                else:
                    if task:
                        if not self._child_pid:
                            gc.disable()  # https://bugs.python.org/issue1336
                            try:
                                pid = os.fork()
                            except OSError:  # pragma: no cover
                                gc.enable()
                                logger.exception('Fork task worker failed.')
                            else:
                                gc.enable()
                                if pid == 0:  # child
                                    self._run_tasks()  # pragma: no cover
                                else:  # parent
                                    logger.debug('Forked a child worker %d.', pid)
                                    self._child_pid = pid
                        self._monitor_task(task, self._child_pid)
        finally:
            self._unregister_signals()
            self._status = Status.STOPPED
            logger.debug('Stopped PreforkedWorker %d.', os.getpid())

    def _register_signals(self):
        super(PreforkedWorker, self)._register_signals()
        signal.signal(signal.SIGCHLD, ignore_signal)

        self._waker = r, w = non_blocking_pipe()
        self._task_channel = non_blocking_pipe()
        self._result_channel = non_blocking_pipe()
        self._child_pid = None

        signal.set_wakeup_fd(w)

    def _unregister_signals(self):
        signal.set_wakeup_fd(-1)

        os.close(self._waker[0])
        os.close(self._waker[1])
        del self._waker

        os.close(self._task_channel[0])
        os.close(self._task_channel[1])
        del self._task_channel

        os.close(self._result_channel[0])
        os.close(self._result_channel[1])
        del self._result_channel

        signal.signal(signal.SIGCHLD, signal.SIG_DFL)
        super(PreforkedWorker, self)._unregister_signals()

    def _send_task(self, task, pid, now, timeout):
        task_writer = self._task_channel[1]
        data_len = len(task.data)
        data = struct.pack('=I', data_len) + task.data
        if len(data) <= _PIPE_SIZE:  # it won't be blocked
            try_write(task_writer, data)
        else:
            send_timeout = timeout * 0.5  # assume the rest 50% time is not enough for the task
            send_deadline = now + send_timeout
            wlist = (task_writer,)
            while True:
                _, writable_fds, _ = select.select((), wlist, (), 0.1)
                if writable_fds:
                    data, error_no = try_write(task_writer, data)
                    if error_no == 0:  # task has been fully written
                        break

                    if error_no != errno.EAGAIN:
                        logger.error('The task channel to worker %d is broken.', pid)
                        self._rerun_task(task, pid)
                        return False

                    # else not fully written, wait until writable

                if time.time() > send_deadline:  # sending timeout, maybe the child worker is not working
                    logger.error('Sending task to worker %d timeout.', pid)
                    self._rerun_task(task, pid)
                    return False
        return True

    def _monitor_task(self, task, pid):
        """Monitors the task.

        Args:
            task (delayed.task.Task): The task to be monitored.
            pid (int): The worker's pid.
        """
        now = time.time()
        if task.timeout:
            timeout = task.timeout / 1000
        else:
            timeout = self._queue.default_timeout / 1000
        deadline = now + timeout
        kill_deadline = deadline + self._kill_timeout
        waker_reader = self._waker[0]
        result_reader = self._result_channel[0]
        killing = False

        if not self._send_task(task, pid, now, timeout):
            return

        rlist = (waker_reader, result_reader)
        try:
            while True:
                try:
                    readable_fds, _, _ = select.select(rlist, (), (), 0.1)
                    if readable_fds:
                        done = False

                        for fd in readable_fds:
                            if fd == waker_reader:  # catch a signal (maybe SIGCHLD)
                                drain_out(waker_reader)
                                p, exit_status = os.waitpid(pid, os.WNOHANG)
                                if p != 0:  # child has exited
                                    logger.warning('The child worker %d has exited.', p)
                                    self._child_pid = None
                                    if exit_status:
                                        kill_signal = exit_status & _SIGNAL_MASK
                                        if kill_signal:
                                            if self._error_handler:
                                                self._handle_error(task, kill_signal, None)
                                        else:  # task hasn't been run
                                            self._requeue_task(task)
                                            return
                                    done = True
                                    break
                            else:  # task has finished or child has exited
                                if read_all(fd):  # task has finished
                                    done = True
                                    break
                                # else child has exited

                        if done:
                            break
                except OSError as e:  # pragma: no cover
                    if e.errno != errno.EINTR:
                        raise
                except select.error as e:  # pragma: no cover
                    if e.args[0] != errno.EINTR:
                        raise

                now = time.time()
                if now >= deadline:
                    if now >= kill_deadline:
                        os.kill(pid, signal.SIGKILL)
                    elif not killing:
                        os.kill(pid, signal.SIGTERM)
                        killing = True
        except Exception:  # pragma: no cover
            logger.exception('Monitor task %d error.', task.id)
            if self._error_handler:
                self._error_handler(task, 0, sys.exc_info())

        self._release_task(task)

    def _rerun_task(self, task, pid):
        """Kills the child worker and requeues the task.

        Args:
            task (delayed.task.Task): The task to be rerun.
            pid (int): The child worker's pid.
        """
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)
        self._requeue_task(task)

    def _run_tasks(self):
        """Runs tasks.
        The monitor sends the tasks to the worker through a pipe.
        """
        error_code = 1
        try:
            task_reader, task_writer = self._task_channel
            os.close(task_writer)
            del self._task_channel

            result_reader, result_writer = self._result_channel
            os.close(result_reader)
            del self._result_channel

            signal.set_wakeup_fd(-1)
            os.close(self._waker[0])
            os.close(self._waker[1])
            del self._waker

            signal.signal(signal.SIGCHLD, signal.SIG_DFL)
            super(PreforkedWorker, self)._unregister_signals()

            rlist = (task_reader,)

            while True:
                error_code = 1
                try:
                    readable_fds, _, _ = select.select(rlist, (), (), 0.1)
                    if readable_fds:
                        logger.debug('The task channel became readable.')
                        head_data = read1(task_reader)
                        if not head_data or len(head_data) <= 4:
                            logger.error('The task channel is broken.')
                            write_byte(result_writer, b'1')
                            os._exit(error_code)
                            return

                        data_length = struct.unpack('=I', head_data[:4])[0]
                        task_data = head_data[4:]
                        read_length = len(task_data)
                        rest_length = data_length - read_length
                        if rest_length:
                            buf = BytesIO(task_data)
                            while rest_length:
                                readable_fds, _, _ = select.select(rlist, (), (), 0.1)
                                if readable_fds:
                                    logger.debug('The task channel became readable.')
                                    read_length = read_bytes(task_reader, rest_length, buf)
                                    if read_length == 0:
                                        logger.error('The task channel is broken.')
                                        write_byte(result_writer, b'1')
                                        os._exit(error_code)
                                        return
                                    rest_length -= read_length
                            task_data = buf.getvalue()
                            buf.close()

                        try:
                            task = Task.deserialize(task_data)
                        except Exception:
                            logger.exception('Deserialize task failed.')
                            written_bytes = write_byte(result_writer, b'1')
                        else:
                            error_code = 0
                            try:
                                task.run()
                            except Exception:
                                logger.exception('Run task %d failed.', task.id)
                                if self._error_handler:
                                    self._error_handler(task, 0, sys.exc_info())
                                written_bytes = write_byte(result_writer, b'1')
                            else:
                                if self._success_handler:
                                    self._handler_success(task)
                                written_bytes = write_byte(result_writer, b'0')
                            finally:
                                self._release_task(task)
                        if written_bytes == 0:  # cannot write to result_writer, parent maybe exited
                            logger.error('Write to result_writer failed.')
                            os._exit(error_code)
                            return
                except OSError as e:  # pragma: no cover
                    if e.errno != errno.EINTR:
                        raise
                except select.error as e:  # pragma: no cover
                    if e.args[0] != errno.EINTR:
                        raise
        finally:
            os._exit(error_code)
