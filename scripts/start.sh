#!/bin/sh
# One-command local deployment: ./scripts/start.sh [--demo]
# First run creates backend/.env in keyless mock mode; add GROQ_API_KEY and set LLM_PROVIDER=groq
# there to use a real model. --demo resets the simulator and runs the flagship demo via the API.
set -e
cd "$(dirname "$0")/.."

if [ ! -f backend/.env ]; then
  cp backend/.env.example backend/.env
  sed -i.bak 's/^LLM_PROVIDER=.*/LLM_PROVIDER=mock/' backend/.env && rm -f backend/.env.bak
  echo "Created backend/.env with LLM_PROVIDER=mock (no API key needed)."
fi

docker compose up -d --build

printf "Waiting for the backend and frontend to become healthy"
for _ in $(seq 1 60); do
  if docker compose ps --format '{{.Service}} {{.Health}}' | grep -q "^backend healthy" \
     && docker compose ps --format '{{.Service}} {{.Health}}' | grep -q "^frontend healthy"; then
    echo " ready."
    break
  fi
  printf "."
  sleep 3
done

if [ "$1" = "--demo" ]; then
  docker compose exec -T backend python -m app.demo.flagship --reset
fi

echo "OpsPilot: http://localhost:3000  (operator/operator; approve as admin/admin)"
