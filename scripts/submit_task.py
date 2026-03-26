import dotenv
from opencase import OpenCaseClient

config_file="../backend/.env.test"
client = OpenCaseClient(base_url="http://127.0.0.1:8000")

admin_email = dotenv.get_key(config_file, "OPENCASE_ADMIN_EMAIL")
admin_password = dotenv.get_key(config_file, "OPENCASE_ADMIN_PASSWORD")
print(f"Logging in with email: {admin_email}")

client.login(email=admin_email, password=admin_password)

# submit long-running task
client.submit_task(task_name="sleep", kwargs={"seconds": 30})

# Submit ping task
result = client.submit_task(task_name="ping")
print(f"Submitted: {result.task_id}")

# Poll for result
task = client.get_task(result.task_id)
print(f"Status: {task.status}, Result: {task.result}")

client.logout()
