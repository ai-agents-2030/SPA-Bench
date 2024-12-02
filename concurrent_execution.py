import concurrent.futures
import queue


def run_task_with_multi_devices(run_task, task_arg_list, devices):
    # Task queue
    task_queue = queue.Queue()

    # Fill the task queue
    for task_arg in task_arg_list:
        task_queue.put(task_arg)

    def worker(device):
        while not task_queue.empty():
            try:
                # Get the next task
                task_arg = task_queue.get_nowait()
            except queue.Empty:
                break

            try:
                run_task(*task_arg, device)
            except Exception as e:
                print(f"Error executing task {task_arg} on {device}: {e}")
            finally:
                # Mark the task as done
                task_queue.task_done()

    # Use ThreadPoolExecutor to manage the concurrent execution
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(devices)) as executor:
        # Submit a worker for each device
        futures = [executor.submit(worker, device) for device in devices]

        # Wait for all tasks to be completed
        concurrent.futures.wait(futures)
