uvicorn main:app --reload

docker-compose up -d

docker logs -f hhlifter-worker-1

@rem watchfiles "celery -A worker.celery_app worker --loglevel=info -P solo" --filter python
watchfiles "celery -A worker.celery_app beat --loglevel=info -P solo" --filter python