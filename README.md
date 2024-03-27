# delayed
[![Build Status](https://github.com/keakon/delayed/actions/workflows/python.yml/badge.svg)](https://github.com/keakon/delayed/actions)
[![Coverage](https://codecov.io/gh/keakon/delayed/branch/master/graph/badge.svg)](https://codecov.io/gh/keakon/delayed)

Delayed is a simple but robust task queue inspired by [rq](https://python-rq.org/).

## Features

* Robust: all the enqueued tasks will run exactly once, even if the worker got killed at any time.
* Clean: finished tasks (including failed) take no space of your Redis.
* Distributed: workers as more as needed can run in the same time without further config.
* Portable: its [Go](https://github.com/keakon/go-delayed) and [Python](https://github.com/keakon/delayed) version can call each other.

## Requirements

1. Python 3.7 or later, tested on CPython 3.7 - 3.12. Versions before 1.0 have also been tested on CPython 2.7, PyPy and PyPy3.
2. To gracefully stop the workers, Unix-like systems (with Unix signal) are required, tested on Ubuntu 22.04 and macOS Monterey 12.
3. Redis 2.6.0 or later (with Lua scripts).

## Getting started

1. Run a redis server:

    ```bash
    $ redis-server
    ```

2. Install delayed:

    ```bash
    $ pip install delayed
    ```

3. Create a task queue:

    ```python
    import redis
    from delayed.queue import Queue

    conn = redis.Redis()
    queue = Queue(name='default', conn=conn)
    ```


4. Enqueue tasks:
    * Four ways to enqueue Python tasks:
        1. Define a task function and enqueue it:

            ```python
            from delayed.delay import delayed

            delayed = delayed(queue)

            @delayed
            def delayed_add(a, b):
                return a + b

            delayed_add.delay(1, 2)  # enqueue delayed_add
            delayed_add.delay(1, b=2)  # same as above
            delayed_add(1, 2)  # call it immediately
            ```
        2. Directly enqueue a function:

            ```python
            from delayed.delay import delayed

            delayed = delayed(queue)

            def add(a, b):
                return a + b

            delayed(add).delay(1, 2)
            delayed(add).delay(1, b=2)  # same as above
            ```
        3. Create a task and enqueue it:

            ```python
            from delayed.task import PyTask

            def add(a, b):
                return a + b

            task = PyTask(func=add, args=(1,), kwargs={'b': 2})
            queue.enqueue(task)
            ```
        4. Enqueue a predefined task function without importing it (the fastest and lightest way):

            ```python
            from delayed.task import PyTask

            task = PyTask(func='test:add', args=(1,), kwargs={'b': 2})
            queue.enqueue(task)
            ```
    * Enqueue Go tasks:

        ```python
            from delayed.task import GoTask

            task = GoTask(func_path='syscall.Kill', args=(0, 1))
            queue.enqueue(task)

            task = GoTask(func_path='fmt.Printf', args=('%d %s\n', [1, 'test']))  # the variadic argument needs to be a list or tuple
            queue.enqueue(task)

            task = GoTask('fmt.Println', (1, 'test'))  # if the variadic argument is the only argument, it's not required to wrap it with a list or tuple
            queue.enqueue(task)
        ```

5. Run a task worker (or more) in a separated process:

    ```python
    import redis
    from delayed.queue import Queue
    from delayed.worker import Worker

    conn = redis.Redis()
    queue = Queue(name='default', conn=conn)
    worker = Worker(queue=queue)
    worker.run()
    ```

6. Run a task sweeper in a separated process to recovery lost tasks (mainly due to the worker got killed):

    ```python
    import redis
    from delayed.queue import Queue
    from delayed.sweeper import Sweeper

    conn = redis.Redis()
    queue = Queue(name='default', conn=conn)
    sweeper = Sweeper(queues=[queue])
    sweeper.run()
    ```

## Examples

See [examples](examples).

    ```bash
    $ redis-server &
    $ pip install delayed
    $ python -m examples.sweeper &
    $ python -m examples.worker &
    $ python -m examples.caller
    ```

## QA

1. **Q: What's the limitation on a task function?**  
A: A Python task function should be defined in module level (except the `__main__` module).
Its `args` and `kwargs` should be serializable by [MessagePack](https://msgpack.org/).
After deserializing, the type of `args` and `kwargs` passed to the task function might be changed (tuple -> list), so it should take care of this change.

2. **Q: What's the `name` param of a queue?**  
A: It's the key used to store the tasks of the queue. A queue with name "default" will use those keys:
    * default: list, enqueued tasks.
    * default_noti: list, the same length as enqueued tasks.
    * default_processing: hash, the processing task of workers.

3. **Q: What's lost tasks?**  
A: There are 2 situations a task might get lost:
    * a worker popped a task notification, then got killed before dequeueing the task.
    * a worker dequeued a task, then got killed before releasing the task.

4. **Q: How to recovery lost tasks?**  
A: Runs a sweeper. It dose two things:
    * it keeps the task notification length the same as the task queue.
    * it checks the processing list, if the worker is dead, moves the processing task back to the task queue.

5. **Q: How to turn on the debug logs?**  
A: Adds a `logging.DEBUG` level handler to `delayed.logger.logger`. The simplest way is to call `delayed.logger.setup_logger()`:
    ```python
    from delayed.logger import setup_logger

    setup_logger()
    ```

## Release notes

* 1.0:
    1. Python 2.7 is not supported anymore. (BREAKING CHANGE)
    2. Supports Go, adds `GoTask`.
    3. Use MessagePack instead of pickle to serialize / deserialize tasks. (BREAKING CHANGE)
    4. Removes `ForkedWorker` and `PreforkedWorker`. You can use `Worker` instead. (BREAKING CHANGE)
    5. Changes params of `Queue()`, removes `default_timeout`, `requeue_timeout` and `busy_len`, adds `dequeue_timeout` and `keep_alive_timeout`. (BREAKING CHANGE)
    6. Rename `Task` to `PyTask`. (BREAKING CHANGE)
    7. Removes those properties of `PyTask`: `id`, `func_path`, `args` and `kwargs`. (BREAKING CHANGE)
    8. Removes those params of `PyTask()`: `id`, `timeout`, `prior` and `error_handler_path`. (BREAKING CHANGE)
    9. Removes `PyTask.create()`. You can use `PyTask()` instead. (BREAKING CHANGE)
    10. Rename `func_path` param of `PyTask()` to `func`, it accepts both `callable` and `str`. (BREAKING CHANGE)
    11. Removes `delayed.delay()`. Removes params of `delayed.delayed()`. (BREAKING CHANGE)

* 0.11:
    1. Sleeps random time when a `Worker` fails to pop a `task` before retrying.

* 0.10:
    1. The `Sweeper` can handle multiple queues now. Its `queue` param has been changed to `queues`. (BREAKING CHANGE)
    2. Changes the separator between `module_path` and `func_name` from `.` to `:`. (BREAKING CHANGE)

* 0.9:
    1. Adds `prior` and `error_handler` params to `deleyed.delayed()`, removes its `timeout()` method. (BREAKING CHANGE)
    2. Adds [examples](examples).

* 0.8:
    1. The `Task` struct has been changed, it's not compatible with older versions. (BREAKING CHANGE)
        * Removes `module_name` and `func_name` from `Task`, adds `func_path` instead.
        * Adds `error_handler_path` to `Task`.
    2. Removes `success_handler` and `error_handler` from `Worker`. (BREAKING CHANGE)

* 0.7:
    1. Implements prior task.

* 0.6:
    1. Adds `dequeued_len()` and `index` to `Queue`.

* 0.5:
    1. Adds `delayed.task.set_pickle_protocol_version()`.

* 0.4:
    1. Refactories and fixes bugs.

* 0.3:
    1. Changes param `second` to `timeout` for `delayed.delayed()`. (BREAKING CHANGE)
    2. Adds debug log.

* 0.2:
    1. Adds `timeout()` to `delayed.delayed()`.

* 0.1:
    1. Init version.
