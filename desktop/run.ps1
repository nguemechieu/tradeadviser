Write-Host "🚀 Starting Sopotek Quant System..."

docker compose pull
docker compose up --build -d
docker tag sopotek-quant-system:latest bigbossmanager/sopotek-quant-system:latest
docker push bigbossmanager/sopotek-quant-system:latest

Write-Host "✅ System is running!"
Write-Host "🌐 Open: http://localhost:6080"