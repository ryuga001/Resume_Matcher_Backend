"""
Worker: listens on the 'bulk_content_generation' queue and generates content for ALL subtopics
sequentially — natural rate-limit throttling for Gemini free tier.

Run from the backend/ directory:
    python workers/bulk_content_worker.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from common.rabbitmq import consume
from courses.task_handlers import handle_generate_all_content
from courses.models import Subtopic

QUEUE = "bulk_content_generation"


def _reset_stale() -> None:
    Subtopic.objects.filter(status="generating").update(status="pending")


def callback(ch, method, _properties, body: bytes) -> None:
    msg       = json.loads(body)
    course_id = str(msg.get("course_id", ""))
    print(f"[bulk_content_worker] course={course_id}")
    try:
        result = handle_generate_all_content(course_id)
        print(f"[bulk_content_worker] done={result}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as exc:
        print(f"[bulk_content_worker] error: {exc}")
        ch.basic_ack(delivery_tag=method.delivery_tag)


if __name__ == "__main__":
    try:
        _reset_stale()
    except Exception as exc:
        print(f"[bulk_content_worker] warning: could not reset stale statuses: {exc}")
    consume(QUEUE, callback)
