import time
import dotenv
from gideon import Client

BASE_URL = "http://127.0.0.1:8000"

def submit_long_running_task(client: Client) -> None:
    print("Submitting long-running task (sleep for 30 seconds)...")
    result = client.submit_task(task_name="sleep", kwargs={"seconds": 30})
    print(f"Submitted: {result.task_id}")

def submit_ping_task(client: Client) -> None:
    print("Submitting ping task...")
    result = client.submit_task(task_name="ping")
    print(f"Submitted: {result.task_id}")
    return result

def wait_for_task_result(client: Client, task_id: str) -> None:
    print(f"Waiting for task {task_id} to complete...")
    while True:
        task = client.get_task(task_id)
        if task.status == "completed":
            print(f"Task {task_id} completed with result: {task.result}")
            break
        elif task.status == "failed":
            print(f"Task {task_id} failed.")
            break
        else:
            print(f"Task {task_id} status: {task.status}. Waiting...")
            time.sleep(5)

def main(config_file: str) -> None:

    with Client(base_url=BASE_URL) as client:

        admin_email = dotenv.get_key(config_file, "GIDEON_ADMIN_EMAIL")
        admin_password = dotenv.get_key(config_file, "GIDEON_ADMIN_PASSWORD")
        print(f"Logging in with email: {admin_email}")

        client.login(email=admin_email, password=admin_password)

        submit_long_running_task(client)

        ping_result = submit_ping_task(client)
        wait_for_task_result(client, ping_result.task_id)

        client.logout()


if __name__ == "__main__":
    main(config_file=".env")
