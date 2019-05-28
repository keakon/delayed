# delayed ![Travis CI test result](https://travis-ci.org/keakon/delayed.svg?branch=master)

Delayed is a simple but robust task queue inspired by [rq](https://python-rq.org/).

## Features

* Robust: all the enqueued tasks will run exactly once, even if the worker got killed at any time.
* Clean: finished tasks (including failed) won't take the space of your Redis.
* Distributed: workers as more as needed can run in the same time without further config.

## Requirements

1. Python 2.7 or later. (Tested on Python 2.7, 3.3 - 3.7 and PyPy 3.5.)
2. Most UNIX-like systems (with os.fork() and select.poll() implemented). (Tested on Ubuntu and macOS.)
3. Redis 2.6.0 or later.

## Getting started

1. Run a redis server:

    ```bash
    $ redis-server
    ```

2. Create a task queue:

    ```python
    import redis
    from delayed.queue import Queue

    conn = redis.Redis()
    queue = Queue(name='default', conn=conn)
    ```

3. Two ways to enqueue a task:

    * Define a task function and enqueue it:

        ```python
        from delayed.delay import delay

        delay = delay(queue)
        
        @delay
        def delayed_add(a, b):
            return a + b

        delayed_add.delay(1, 2)  # enqueue delayed_add
        delayed_add.delay(1, b=2)  # same as above
        delayed_add(1, 2)  # call it immediately
        ```

    * Directly enqueue a function:

        ```python
        from delayed.delay import delayed

        delayed = delayed(queue)

        def add(a, b):
            return a + b
        
        delayed(add)(1, 2)
        delayed(add)(1, b=2)  # same as above
        ```

4. Run a task worker (or more) in a separated process:

    ```python
    import redis
    from delayed.queue import Queue
    from delayed.worker import ForkedWorker

    conn = redis.Redis()
    queue = Queue(name='default', conn=conn)
    worker = ForkedWorker(queue=queue)
    worker.run()
    ``` 

5. Run a task sweeper in a separated process to recovery lost tasks (mainly due to the worker got killed):

    ```python
    import redis
    from delayed.queue import Queue
    from delayed.sweeper import Sweeper

    conn = redis.Redis()
    queue = Queue(name='default', conn=conn)
    sweeper = Sweeper(queue=queue)
    sweeper.run()
    ``` 

## QA

1. **Q: What's the "name" param of a queue?**  
A: It's the key used to store the tasks of the queue. A queue with name "default" will use those keys:
    * default: list, enqueued tasks
    * default_id: str, the next task id
    * default_noti: list, the same length as enqueued tasks
    * default_enqueued: sorted set, enqueued tasks with their enqueued timestamp 
    * default_dequeued: sorted set, dequeued tasks with their dequeued timestamp

2. **Q: Why the worker is slow?**  
A: The "ForkedWorker" forks a new process for each new task. So all the tasks are isolated and you won't leak memory.  
To reduce the overhead of forking processes and importing modules, you can switch to "PreforkedWorker":

    ```python
    import redis
    from delayed.queue import Queue
    from delayed.worker import PreforkedWorker

    conn = redis.Redis()
    queue = Queue(name='default', conn=conn)
    worker = PreforkedWorker(queue=queue)
    worker.run()
    ``` 

3. **Q: How does a forked worker run?**  
A: It runs such a loop:
    1. It dequeues a task from the queue periodically.
    2. It forks a child process to run the task.
    3. It kills the child process if the child runs out of time.
    4. When the child process exits, it releases the task.

4. **Q: How does a preforked worker run?**  
A: It runs such a loop:
    1. It dequeues a task from the queue periodically.
    2. If it has no child process, it forks a new one.
    3. It sends the task through a pipe to the child.
    4. It kills the child process if the child runs out of time.
    5. When the child process exits or it received result from the pipe, it releases the task.

5. **Q: How does the child process of a worker run?**  
A: the child of a forked worker just runs the task, unmarks the task as dequeued, then exits.
The child of a preforked worker runs such a loop:
    1. It tries to receive a task from the pipe.
    2. If the pipe has been closed, it exits.
    3. It runs the task.
    4. It sends the task result to the pipe.
    5. It releases the task.

6. **Q: What's lost tasks?**  
A: There are 2 situations a task might get lost:
    * a worker popped a task notification, then got killed before dequeueing the task.
    * a worker dequeued a task, then both the monitor and its child process got killed before they release the task.

7. **Q: How to recovery lost tasks?**  
A: Run a sweeper. It dose two things:
    * it keeps the task notification length the same as the task queue. 
    * it moves the timeout dequeued tasks to the task queue.

8. **Q: How to set the timeout of tasks?**  
A: You can set the default_timeout of a queue or timeout of a task:

    ```python
    from delayed.delay import delay_in_time

    queue = Queue('default', conn, default_timeout=60)
    
    delayed_add.timeout(10)(1, 2)
    
    delay_in_time = delay_in_time(queue)
    delay_in_time(add, timeout=10)(1, 2)
    ```

9. **Q: How to handle the finished tasks?**  
A: Set the success_handler and error_handler of the worker:

    ```python
    def success_handler(task):
        logging.info('task %d finished', task.id)
        
    def error_handler(task, kill_signal, exc_info):
        if kill_signal:
            logging.error('task %d got killed by signal %d', task.id, kill_signal)
        else:
            logging.exception('task %d failed', exc_info=exc_info)
            
    worker = PreforkedWorker(Queue, success_handler=success_handler, error_handler=error_handler)
    ```

10. **Q: Why does sometimes both success_handler and error_handler be called for a single task?**  
A: When the child process got killed after the success_handler be called, or the monitor process got killed but the child process still finished the task, both handlers would be called. You can consider it as successful. 