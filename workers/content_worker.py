"""
Worker: listens on the 'content_generation' queue and generates content for a single subtopic.

Run from the backend/ directory:
    python workers/content_worker.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from common.rabbitmq import consume
from courses.task_handlers import handle_generate_subtopic_content
from courses.models import Subtopic

QUEUE = "content_generation"


def _reset_stale() -> None:
    Subtopic.objects.filter(status="generating").update(status="pending")


def callback(ch, method, _properties, body: bytes) -> None:
    msg       = json.loads(body)
    course_id = str(msg.get("course_id", ""))
    order     = int(msg.get("order", 0))
    print(f"[content_worker] course={course_id} order={order}")
    try:
        handle_generate_subtopic_content(course_id, order)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as exc:
        print(f"[content_worker] error: {exc}")
        ch.basic_ack(delivery_tag=method.delivery_tag)  # ack to avoid infinite requeue


if __name__ == "__main__":
    try:
        _reset_stale()
    except Exception as exc:
        print(f"[content_worker] warning: could not reset stale statuses: {exc}")
    consume(QUEUE, callback)
