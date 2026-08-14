#!/bin/bash
# start_backend.sh - Launcher for GIS Backend Microservices

# Clear screen
clear

echo "========================================================="
echo "        Starting GIS Backend Microservices               "
echo "========================================================="

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BACKEND_DIR"

# Function to stop background processes on exit
cleanup() {
  echo ""
  echo "Stopping services..."
  kill $ASSET_PID $NOTIFY_PID $KPI_PID $GATEWAY_PID 2>/dev/null || true
  exit 0
}
trap cleanup SIGINT SIGTERM EXIT

echo "🚀 Starting Asset Microservice on port 8001..."
./.venv/bin/python -m uvicorn services.asset.main:app --host 127.0.0.1 --port 8001 > asset.log 2>&1 &
ASSET_PID=$!

echo "🚀 Starting Notification Microservice on port 8002..."
./.venv/bin/python -m uvicorn services.notification.main:app --host 127.0.0.1 --port 8002 > notification.log 2>&1 &
NOTIFY_PID=$!

echo "🚀 Starting KPI Microservice on port 8003..."
./.venv/bin/python -m uvicorn services.kpi.main:app --host 127.0.0.1 --port 8003 > kpi.log 2>&1 &
KPI_PID=$!

echo "🚀 Starting API Gateway on port 8000..."
./.venv/bin/python -m uvicorn services.gateway.main:app --host 0.0.0.0 --port 8000 > gateway.log 2>&1 &
GATEWAY_PID=$!

# Wait for backend gateway to be ready
echo "⏳ Waiting for API Gateway to start..."
until curl --output /dev/null --silent --fail http://127.0.0.1:8000/health; do
    printf '.'
    sleep 0.5
done
echo " Done!"

echo "========================================================="
echo "   Backend services are running!"
echo "   - API Gateway: http://localhost:8000"
echo "   - Asset Microservice: port 8001"
echo "   - Notification Microservice: port 8002"
echo "   - KPI Microservice: port 8003"
echo "   Press Ctrl+C to stop all backend services."
echo "========================================================="

# Keep script running to monitor processes
wait
