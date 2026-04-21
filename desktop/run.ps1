Write-Host "🚀 Starting TradeAdviser..."

docker compose pull
docker compose up --build -d
docker tag sopotek-quant-system:latest bigbossmanager/tradeadviser:latest
docker push bigbossmanager/sopotek-quant-system:latest

Write-Host "✅ System is running!"
Write-Host "🌐 Open: http://localhost:6080"