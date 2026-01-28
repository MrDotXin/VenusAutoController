"""SSH隧道代理服务 - 入口文件"""
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core import get_tunnel, start_heartbeat, stop_heartbeat, stop_tunnel
from .routers import proxy_router, experiment_router, camera_router, rtmp_router
from .services import rtmp_server

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    # SSH隧道
    try:
        get_tunnel()
        start_heartbeat()
        logger.info("SSH隧道已建立")
    except Exception as e:
        logger.error(f"SSH隧道建立失败: {e}")
    
    # RTMP服务器
    rtmp_task = asyncio.create_task(rtmp_server.start(port=1935))
    logger.info("RTMP服务器已启动: rtmp://0.0.0.0:1935")
    
    yield
    
    # 清理
    rtmp_server.stop()
    rtmp_task.cancel()
    stop_heartbeat()
    stop_tunnel()


app = FastAPI(
    title="SSH Proxy Server",
    description="SSH隧道代理服务",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(experiment_router)
app.include_router(camera_router)
app.include_router(rtmp_router)
app.include_router(proxy_router)  # 通配路由放最后


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=5000, reload=True)
