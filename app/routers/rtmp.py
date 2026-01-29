"""
RTMP 视频流路由
RTMP 由 SRS Docker 处理

前端播放:
- HTTP-FLV: https://venusfactory.cn/venus-auto-camera/live/{stream_key}.flv
- HLS: https://venusfactory.cn/venus-auto-camera/live/{stream_key}.m3u8
"""
from fastapi import APIRouter

from ..services.rtmp_server import rtmp_server

router = APIRouter(prefix="/rtmp", tags=["RTMP视频流"])


@router.get("/list")
async def list_streams():
    """
    列出所有在线的 RTMP 流
    
    返回 SRS 上当前正在推流的所有流
    """
    return {"success": True, "data": rtmp_server.list_streams()}