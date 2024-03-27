# -*- coding: utf-8 -*-

from typing import Optional, Union

import redis

from .logger import logger
from .task import PyTask


# KEYS: queue_name, processing_key
# ARGV: worker_id
_DEQUEUE_SCRIPT = '''local task = redis.call('lpop', KEYS[1])
if task == nil then
    return nil
end
redis.call('hset', KEYS[2], ARGV[1], task)
return task'''

# KEYS: queue_name, noti_key, processing_key
_REQUEUE_LOST_SCRIPT = '''local queue_len = redis.call('llen', KEYS[1])
local noti_len = redis.call('llen', KEYS[2])
local count = queue_len - noti_len
local processing_tasks = redis.call('hgetall', KEYS[3])
for i = 1, #processing_tasks, 2 do
    local worker_id = processing_tasks[i]
    local worker_alive = redis.call('get', worker_id)
    if not worker_alive then
        count = count + 1
        redis.call('rpush', KEYS[1], processing_tasks[i + 1])
        redis.call('hdel', KEYS[3], worker_id)
    end
end
if count > 0 then
    local noti_array = {}
    for i = 1, count , 1 do
        table.insert(noti_array, '1')
    end
    redis.call('lpush', KEYS[2], unpack(noti_array))
end
return count'''

_NOTI_KEY_SUFFIX = '_noti'
_PROCESSING_KEY_SUFFIX = '_processing'


class Queue:
    """Queue is the class of a task queue.

    Args:
        name (str): The task queue name.
        conn (redis.Redis): A redis connection.
        dequeue_timeout (int or float): The dequeue timeout in seconds of the task queue.
            The task queue will block at most `dequeue_timeout` seconds for receiving a new task.
        keep_alive_timeout (int or float): The keep alive timeout in seconds of the worker.
    """

    def __init__(self, name: str, conn: redis.Redis, dequeue_timeout: Union[int, float] = 1, keep_alive_timeout: Union[int, float] = 60):
        self._worker_id: Optional[bytes] = None
        self._name = name
        self._noti_key = name + _NOTI_KEY_SUFFIX
        self._processing_key = name + _PROCESSING_KEY_SUFFIX
        self._conn = conn
        self._dequeue_timeout = dequeue_timeout
        self._keep_alive_timeout = keep_alive_timeout
        self._dequeue_script = conn.register_script(_DEQUEUE_SCRIPT)
        self._requeue_lost_script = conn.register_script(_REQUEUE_LOST_SCRIPT)

    def enqueue(self, task: PyTask):
        """Enqueues a task to the queue.

        Args:
            task (delayed.task.PyTask or delayed.task.GoTask): The task to be enqueued.
        """
        logger.debug('Enqueuing task %s.', task._func_path)
        data = task.serialize()
        with self._conn.pipeline() as pipe:
            pipe.rpush(self._name, data)
            pipe.rpush(self._noti_key, '1')
            pipe.execute()
        logger.debug('Enqueued task %s.', task._func_path)

    def dequeue(self) -> Optional[PyTask]:
        """Dequeues a task from the queue.

        Returns:
            delayed.task.PyTask or None: The dequeued task, or None if the queue is empty.
        """
        if self._conn.blpop(self._noti_key, self._dequeue_timeout):
            logger.debug('Popped a task.')
            data = self._dequeue_script(
                keys=(self._name, self._processing_key),
                args=(self._worker_id,))
            if data:
                task = PyTask.deserialize(data)
                logger.debug('Dequeued task %s.', task._func_path)
                return task

    def release(self):
        """Releases the currently dequeued task.
        It should be called after finishing a task.
        """
        logger.debug('Releasing the task of worker %s.', self._worker_id)
        self._conn.hdel(self._processing_key, self._worker_id)
        logger.debug('Released the task of worker %s.', self._worker_id)

    def len(self) -> int:
        """Returns the length of the queue."""
        return self._conn.llen(self._name)

    def requeue_lost(self) -> int:
        """Requeues lost tasks.
        It should be called periodically to prevent losing tasks.
        The lost tasks were those popped from the queue, but its dead worker hadn't released it.

        Returns:
            int: The requeued task count.
        """
        count = self._requeue_lost_script(
            keys=(self._name, self._noti_key, self._processing_key))
        if count >= 1:
            if count == 1:
                logger.debug('Requeued 1 lost task.')
            else:
                logger.debug('Requeued %d lost tasks.', count)
        return count

    def keep_alive(self):
        """Set the worker of the queue alive."""
        self._conn.setex(self._worker_id, self._keep_alive_timeout, 1)
        logger.debug('Worker %s is alive.', self._worker_id)

    def _die(self):
        """Set the worker of the queue dead."""
        self._conn.delete(self._worker_id)
        logger.debug('Worker %s dies.', self._worker_id)
