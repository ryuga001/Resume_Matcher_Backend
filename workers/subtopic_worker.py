"""
Worker: listens on the 'subtopics_generation' queue and generates course subtopics.

Run from the backend/ directory:
    python workers/subtopic_worker.py
"""
import json
import os
import sys

# Bootstrap Django before importing any app code
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from common.rabbitmq import consume
from courses.task_handlers import handle_generate_subtopics
from courses.models import Subtopic

QUEUE = "subtopics_generation"


def _reset_stale() -> None:
    """On startup reset any 'generating' subtopics left by a crashed worker."""
    Subtopic.objects.filter(status="generating").update(status="pending")


def callback(ch, method, _properties, body: bytes) -> None:
    msg = json.loads(body)
    task_id   = msg.get("task_id", "")
    course_id = msg.get("course_id", "")
    print(f"[subtopic_worker] task={task_id} course={course_id}")
    try:
        handle_generate_subtopics(task_id, course_id)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as exc:
        print(f"[subtopic_worker] error: {exc}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


if __name__ == "__main__":
    try:
        _reset_stale()
    except Exception as exc:
        print(f"[subtopic_worker] warning: could not reset stale statuses: {exc}")
    consume(QUEUE, callback)
