# -*- coding: utf-8 -*-

from .common import CONN, DELAYED, QUEUE, QUEUE_NAME


@DELAYED
def delayed_func(a, b):
    return a + b


@DELAYED(retry=1)
def delayed_func2(a, b):
    return a + b


def delayed_func3(a, b):
    return a + b


def delayed_func4(a, b):
    return a + b


delayed_func3 = DELAYED(delayed_func3, retry=2)
delayed_func4 = DELAYED(retry=3)(delayed_func4)


def test_delayed():
    CONN.delete(QUEUE_NAME)

    assert delayed_func(1, 2) == 3
    assert delayed_func.__name__ == 'delayed_func'

    delayed_func.delay(1, 2)
    assert QUEUE.len() == 1
    task = QUEUE.dequeue()
    assert task is not None
    assert task._retry == 0
    assert task.execute() == 3
    QUEUE.release()

    assert delayed_func2(1, 2) == 3
    assert delayed_func2.__name__ == 'delayed_func2'

    delayed_func2.delay(1, 2)
    assert QUEUE.len() == 1
    task = QUEUE.dequeue()
    assert task is not None
    assert task._retry == 1
    assert task.execute() == 3
    QUEUE.release()

    assert delayed_func3(1, 2) == 3
    assert delayed_func3.__name__ == 'delayed_func3'

    delayed_func3.delay(1, 2)
    assert QUEUE.len() == 1
    task = QUEUE.dequeue()
    assert task is not None
    assert task._retry == 2
    assert task.execute() == 3
    QUEUE.release()

    assert delayed_func4(1, 2) == 3
    assert delayed_func4.__name__ == 'delayed_func4'

    delayed_func4.delay(1, 2)
    assert QUEUE.len() == 1
    task = QUEUE.dequeue()
    assert task is not None
    assert task._retry == 3
    assert task.execute() == 3
    QUEUE.release()