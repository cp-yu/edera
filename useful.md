  curl -X POST http://127.0.0.1:8000/api/dags/uzi-skill-analysis/run \
    -H 'Content-Type: application/json' \
    -d '{"ticker":"00100.HK"}'
