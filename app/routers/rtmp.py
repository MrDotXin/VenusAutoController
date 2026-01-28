"""
RTMP视频流路由
RTMP由SRS Docker处理，此服务提供截图功能

前端播放视频流:
- HTTP-FLV: http://服务器:5002/live/camera1.flv
- HLS: http://服务器:5002/live/camera1.m3u8
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from ..services.rtmp_server import rtmp_server

router = APIRouter(prefix="/rtmp", tags=["RTMP视频流"])


@router.get("/list")
async def list_streams():
    """
    列出所有在线的RTMP流（从SRS获取）
    
    返回 SRS 上当前正在推流的所有流
    """
    return {"success": True, "data": rtmp_server.list_srs_streams()}


@router.get("/snapshots")
async def list_snapshots():
    """列出所有已注册截图的流"""
    return {"success": True, "data": rtmp_server.list_streams()}


@router.get("/snapshot/{stream_key}")
async def get_snapshot(stream_key: str):
    """
    获取流快照
    
    首次请求会自动注册流并开始定时截图
    """
    frame = rtmp_server.get_frame(stream_key)
    if frame:
        return Response(content=frame, media_type="image/jpeg")
    raise HTTPException(status_code=404, detail=f"流 {stream_key} 无可用图片，请确认SRS有该流推送")


@router.get("/status/{stream_key}")
async def get_stream_status(stream_key: str):
    """获取流状态"""
    status = rtmp_server.get_status(stream_key)
    if status:
        return {"success": True, "data": status}
    return {"success": False, "message": f"流 {stream_key} 未注册"}


@router.delete("/remove/{stream_key}")
async def remove_stream(stream_key: str):
    """移除流（停止截图）"""
    if rtmp_server.remove_stream(stream_key):
        return {"success": True, "message": f"流 {stream_key} 已移除"}
    return {"success": False, "message": f"流 {stream_key} 不存在"}
