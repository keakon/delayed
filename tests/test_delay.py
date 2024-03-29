# -*- coding: utf-8 -*-

from .common import CONN, DELAYED, QUEUE, QUEUE_NAME


@DELAYED
def delayed_func(a, b):
    return a + b


def test_delayed():
    CONN.delete(QUEUE_NAME)

    assert delayed_func(1, 2) == 3
    assert delayed_func.__name__ == 'delayed_func'

    delayed_func.delay(1, 2)
    assert QUEUE.len() == 1
    task = QUEUE.dequeue()
    assert task is not None
    assert task.execute() == 3
    QUEUE.release()
