#!/bin/bash

ROOT=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

cd "${ROOT}"
cp .env "${ROOT}/../example_services"


cd "${ROOT}"
source venv/bin/activate
cp ${ROOT}/credentials.json ${ROOT}/../example_services/demo_service2
cd ${ROOT}/../example_services/demo_service2
python -m uvicorn main:app --port=1998 &
PID1=$!

cd "${ROOT}"
source venv/bin/activate
cd ${ROOT}/../example_services/demo_service1
python -m uvicorn main:app --port=1999 &
PID2=$!

wait $PID1
wait $PID2