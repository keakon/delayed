# -*- coding: utf-8 -*-

from delayed.task import PyTask

from .client import queue
from .tasks import func1, func2, DELAYED


DELAYED(func1)(1, 2, x=3)

func2(1, 2, x=3)
func2.delay(1, 2, x=3)

task = PyTask(func='examples.tasks:func1', args=(1, 2), kwargs={'x': 3})
queue.enqueue(task)

task = PyTask(func='examples.tasks:func2', args=(1, 2), kwargs={'x': 3})
queue.enqueue(task)

task = PyTask(func=func1, args=(1, 2), kwargs={'x': 3})
queue.enqueue(task)

task = PyTask(func=func2, args=(1, 2), kwargs={'x': 3})
queue.enqueue(task)
