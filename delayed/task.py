# -*- coding: utf-8 -*-

from importlib import import_module
from typing import Any, Callable, Optional, Union

from msgpack import packb, unpackb

from .constants import SEP
from .logger import logger


class PyTask:
    """PyTask is the class of a Python task.

    Args:
        func (callable or str): The task function or function path.
            The function should be defined in module level (except the `__main__` module).
            The function path format is "module.path:func_name".
        args (list or tuple): Variable length argument list of the task function.
        kwargs (dict): Arbitrary keyword arguments of the task function.
    """

    __slots__ = ['_func_path', '_args', '_kwargs', '_data']

    def __init__(self, func: Union[Callable, str], args: Union[list, tuple, None] = None, kwargs: Optional[dict] = None):
        if isinstance(func, str):
            self._func_path = func
        elif callable(func):
            self._func_path = func.__module__ + SEP + func.__name__
        else:
            raise ValueError('Invalid func %r' % func)
        self._args = () if args is None else args
        self._kwargs = {} if kwargs is None else kwargs
        self._data = None

    def serialize(self) -> Optional[bytes]:
        """Serializes the task to bytes.

        Returns:
            str: The serialized data.
        """
        if self._data is None:
            data = self._func_path, self._args, self._kwargs

            i = 0
            if not self._kwargs:
                i -= 1
                if not self._args:
                    i -= 1
            if i < 0:
                data = data[:i]
            self._data = packb(data)
        return self._data

    @classmethod
    def deserialize(cls, data) -> 'PyTask':
        """Deserialize a task from the bytes.

        Args:
            data (str): The string to be deserialize.

        Returns:
            PyTask: The deserialized task.
        """
        task = cls(*unpackb(data))
        task._data = data
        return task

    def execute(self) -> Any:
        """Executes the task.

        Returns:
            Any: The result of the task function.
        """
        logger.debug('Executing task %s.', self._func_path)
        module_path, func_name = self._func_path.split(SEP, 1)
        module = import_module(module_path)
        func = getattr(module, func_name)
        return func(*self._args, **self._kwargs)


class GoTask:
    """GoTask is the class of a Go task.

    Args:
        id (int or None): The task id.
        func_path (str): The task function path.
            The format is "package/path.func_name".
        args (any): Arguments of the task function.
    """

    __slots__ = ['_func_path', '_args', '_payload', '_data']

    def __init__(self, func_path: str, args: Optional[list] = None):
        self._func_path = func_path
        self._args = args
        self._payload = None
        self._data = None

    def serialize(self) -> Optional[bytes]:
        """Serializes the task to bytes.

        Returns:
            str: The serialized data.
        """
        if self._data is None:
            if self._payload is None and self._args is not None:
                self._payload = packb(self._args)
                data = self._func_path, self._payload
            else:
                data = self._func_path
            self._data = packb(data)
        return self._data
