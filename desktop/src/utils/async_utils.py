import asyncio
import logging
from typing import Callable, Any, Coroutine

logger = logging.getLogger(__name__)


# ==========================================================
# SAFE TASK CREATION
# ==========================================================

def create_task(coro: Coroutine, name: str ):
    """
    Create a background task with error logging
    """
    task = asyncio.create_task(coro)

    if name:
        try:
            task.set_name(name)
        except Exception:
            pass

    task.add_done_callback(_handle_task_exception)

    return task


def _handle_task_exception(task: asyncio.Task):
    """
    Capture task exceptions
    """
    try:
        task.result()
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Async task error: {e}", exc_info=True)


# ==========================================================
# SAFE TASK CANCELLATION
# ==========================================================

async def cancel_task(task: asyncio.Task):
    """
    Safely cancel a running async task
    """
    if task is None:
        return

    if not task.done():
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass


async def cancel_tasks(tasks: list):
    """
    Cancel multiple tasks
    """
    await asyncio.gather(*(cancel_task(t) for t in tasks), return_exceptions=True)


# ==========================================================
# RETRY UTILITY
# ==========================================================

async def retry_async(
        func: Callable,
        retries: int = 3,
        delay: float = 1.0,
        backoff: float = 2.0
) -> Any:
    """
    Retry async function with exponential backoff
    """

    attempt = 0

    while attempt < retries:

        try:
            return await func()

        except Exception as e:

            logger.warning(f"Retry {attempt + 1}/{retries} failed: {e}")

            await asyncio.sleep(delay)

            delay *= backoff
            attempt += 1

    raise RuntimeError("Max retry attempts reached")


# ==========================================================
# PERIODIC TASK
# ==========================================================

async def periodic_task(interval: float, coro: Callable, *args, **kwargs):
    """
    Run async function repeatedly every interval seconds
    """

    while True:

        try:
            await coro(*args, **kwargs)

        except Exception as e:
            logger.error(f"Periodic task error: {e}", exc_info=True)

        await asyncio.sleep(interval)


# ==========================================================
# TIMEOUT WRAPPER
# ==========================================================

async def run_with_timeout(coro: Coroutine, timeout: float):

    try:
        return await asyncio.wait_for(coro, timeout)

    except asyncio.TimeoutError:
        logger.warning("Async operation timed out")


# ==========================================================
# QUEUE WORKER
# ==========================================================

async def queue_worker(queue: asyncio.Queue, handler: Callable):

    while True:

        item = await queue.get()

        try:

            await handler(item)

        except Exception as e:

            logger.error(f"Queue worker error: {e}", exc_info=True)
            traceback.print_exc()

        finally:

            queue.task_done()