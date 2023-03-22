# -*- coding: utf-8 -*-

from delayed.task import PyTask

from .common import func


class TestTask(object):
    def test_create(self):
        task = PyTask.create(func, (1, 2))
        assert task._func_path == 'tests.common:func'
        assert task._args == (1, 2)
        assert task._kwargs == {}

    def test_serialize_and_deserialize(self):
        task = PyTask.create(func, (1, 2))
        data = task.serialize()
        assert data is not None
        assert data == task._data

        task = PyTask.deserialize(data)
        assert task._func_path == 'tests.common:func'
        assert task._args == [1, 2]
        assert task._kwargs == {}

        task = PyTask.create(func, (1,), {'b': 2})
        data = task.serialize()
        task = PyTask.deserialize(data)
        assert task._func_path == 'tests.common:func'
        assert task._args == [1]
        assert task._kwargs == {'b': 2}

        task = PyTask.create(func, kwargs={'a': 1, 'b': 2})
        data = task.serialize()
        task = PyTask.deserialize(data)
        assert task._func_path == 'tests.common:func'
        assert task._args == []
        assert task._kwargs == {'a': 1, 'b': 2}

    def test_execute(self):
        task = PyTask.create(func, (1, 2))
        data = task.serialize()
        task = PyTask.deserialize(data)
        assert task.execute() == 3
