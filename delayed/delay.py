# -*- coding: utf-8 -*-

from typing import Callable, Optional
from functools import wraps

from .queue import Queue
from .task import PyTask


def delayed(queue: Queue):
    """A decorator for defining task functions.
    Calling a delayed function is equivalent to call the raw function.
    Calling the delay() method of a delayed function will enqueue a task.

    Args:
        queue (delayed.queue.Queue): The task queue.

    Returns:
        callable: A decorator.
    """
    def wrapper(func: Optional[Callable] = None, *, retry: int = 0):
        if func:
            @wraps(func)
            def _delay(*args, **kwargs):
                task = PyTask(func, args, kwargs, retry)
                queue.enqueue(task)

            func.delay = _delay
            return func
        else:
            def inner(func: Callable):
                @wraps(func)
                def _delay(*args, **kwargs):
                    task = PyTask(func, args, kwargs, retry)
                    queue.enqueue(task)

                func.delay = _delay
                return func
            return inner
    return wrapper
