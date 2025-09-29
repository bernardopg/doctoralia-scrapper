#!/bin/sh
exec rq worker -u ${REDIS_URL:-redis://redis:6379/0} doctoralia
