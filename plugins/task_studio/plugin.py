from airflow.plugins_manager import AirflowPlugin
from task_studio.routes import app



class TaskStudioPlugin(AirflowPlugin):
    name = "task_studio"

    fastapi_apps = [
        {
            "name": "task_studio",
            "app": app,
            "url_prefix": "/task-studio",
        }
    ]

    react_apps = [
    # 1. Global Task Studio
    {
        "name": "Task Studio",
        "bundle_url": "/task-studio/static/main.umd.cjs",
        "destination": "nav",
        "category": "browse",
        "url_route": "task-studio",
    },

    # 2. Contextual Task Studio
    {
        "name": "Task Studio",
        "bundle_url": "/task-studio/static/main.umd.cjs",
        "destination": "task_instance",
        "url_route": "task-studio-task",
    },
]