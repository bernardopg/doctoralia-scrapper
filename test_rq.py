import os
import redis
from rq import Queue
from rq.job import Job
from rq.registry import StartedJobRegistry, FinishedJobRegistry, FailedJobRegistry

r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
q = Queue("doctoralia", connection=r)
print("Connected")
