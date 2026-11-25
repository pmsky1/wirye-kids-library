#!/bin/bash
# 위례키즈 도서관 통합 실행 스크립트 (백엔드 FastAPI + 프론트엔드 Next.js)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=================================================="
echo "🎈 위례키즈 도서관 웹앱 실행을 시작합니다..."
echo "=================================================="

# 1. 백엔드 실행
echo "🚀 1. 백엔드 FastAPI 서버 구동 중... (http://localhost:8000)"
cd "$ROOT_DIR/backend"
"$ROOT_DIR/backend/venv/bin/uvicorn" main:app --host 0.0.0.0 --port 8000 --reload --reload-dir "$ROOT_DIR/backend" &
BACKEND_PID=$!

# 2. 프론트엔드 실행
echo "💻 2. 프론트엔드 Next.js 구동 중... (http://localhost:3000)"
cd "$ROOT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo "=================================================="
echo "✅ 서비스 구동 완료!"
echo "   - 프론트엔드: http://localhost:3000"
echo "   - 백엔드 API: http://localhost:8000/docs"
echo "   (종료하려면 Ctrl+C 를 누르세요)"
echo "=================================================="

trap "echo '서버를 종료합니다...'; kill $BACKEND_PID $FRONTEND_PID; exit 0" SIGINT SIGTERM

wait
