#!/bin/bash

echo "🚀 Starting Sopotek Quant System..."

docker compose pull
docker compose up --build -d
docker tag sopotek-quant-system:latest bigbossmanager/sopotek-quant-system:latest
docker push bigbossmanager/sopotek-quant-system:latest


echo "✅ System is running!"
echo "🌐 Open: http://localhost:6080"