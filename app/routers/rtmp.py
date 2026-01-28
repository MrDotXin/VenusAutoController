"""
RTMP视频流路由
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse

from ..services.rtmp_server import rtmp_server

router = APIRouter(prefix="/rtmp", tags=["RTMP视频流"])


@router.get("/list")
async def list_streams():
    """列出所有RTMP流"""
    return {"success": True, "data": rtmp_server.list_streams()}


@router.get("/view/{stream_key}")
async def view_stream(stream_key: str):
    """
    查看RTMP视频流 (MJPEG格式)
    
    前端使用:
    <img src="http://服务器/rtmp/view/camera1">
    """
    if stream_key not in rtmp_server.streams:
        raise HTTPException(status_code=404, detail=f"流 {stream_key} 不存在")
    
    return StreamingResponse(
        rtmp_server.generate_mjpeg(stream_key),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@router.get("/snapshot/{stream_key}")
async def get_snapshot(stream_key: str):
    """获取快照"""
    frame = rtmp_server.get_frame(stream_key)
    if frame:
        return Response(content=frame, media_type="image/jpeg")
    raise HTTPException(status_code=404, detail=f"流 {stream_key} 无可用图片")


@router.get("/status/{stream_key}")
async def get_stream_status(stream_key: str):
    """获取流状态"""
    status = rtmp_server.get_status(stream_key)
    if status:
        return {"success": True, "data": status}
    return {"success": False, "message": f"流 {stream_key} 不存在"}


@router.delete("/remove/{stream_key}")
async def remove_stream(stream_key: str):
    """移除流"""
    if rtmp_server.remove_stream(stream_key):
        return {"success": True, "message": f"流 {stream_key} 已移除"}
    return {"success": False, "message": f"流 {stream_key} 不存在"}
