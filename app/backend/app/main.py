import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi import WebSocket
import time

from app.config import settings
from app.database import init_db
from app.websocket import websocket_endpoint

# Import routers
from app.routers import upload, residents, autofill, query, reports, housing, problems, settings as settings_router, appeals, assistant, resident
print(f"[DEBUG] resident module loaded. router.prefix={getattr(resident, 'router', None) and resident.router.prefix}")

# Initialize database tables
init_db()

# Run database upgrade (add missing columns to existing tables)
from app.db_upgrade import run_upgrade
run_upgrade()

app = FastAPI(
    title=settings.APP_NAME,
    description="数邻智算-网格员端 - 社区治理智能辅助系统",
    version="2.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": f"服务器内部错误: {str(exc)}", "data": None}
    )

# Health check
@app.get("/health")
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "version": "2.0.0"}

# Register routers
app.include_router(upload.router, prefix="/api")
app.include_router(residents.router, prefix="/api")
app.include_router(autofill.router, prefix="/api")
app.include_router(query.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(housing.router, prefix="/api")
app.include_router(problems.router, prefix="/api")
app.include_router(settings_router.router, prefix="/api")
app.include_router(appeals.router, prefix="/api")
app.include_router(assistant.router, prefix="/api")
try:
    app.include_router(resident.router, prefix="/api")
    print(f"[DEBUG] Resident router registered. Prefix: {resident.router.prefix}, Routes: {len(resident.router.routes)}")
    for r in resident.router.routes:
        print(f"[DEBUG]   Route: {list(r.methods)} {r.path}")
except Exception as e:
    print(f"[DEBUG] Failed to register resident router: {e}")

# WebSocket endpoint for real-time updates
app.add_api_websocket_route("/api/ws", websocket_endpoint)

# Serve static directories
uploads_dir = os.path.join(os.path.dirname(__file__), "..", "uploads")
reports_dir = os.path.join(os.path.dirname(__file__), "..", "reports")
exports_dir = os.path.join(os.path.dirname(__file__), "..", "exports")

os.makedirs(uploads_dir, exist_ok=True)
os.makedirs(reports_dir, exist_ok=True)
os.makedirs(exports_dir, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")
app.mount("/reports", StaticFiles(directory=reports_dir), name="reports")
app.mount("/exports", StaticFiles(directory=exports_dir), name="exports")

if __name__ == "__main__":
    import uvico