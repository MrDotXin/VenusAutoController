"""
摄像头HTTP推流路由
摄像头通过HTTP POST推送图片，前端通过HTTP GET查看
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response, StreamingResponse

from ..services.camera import stream_receiver

router = APIRouter(prefix="/camera", tags=["摄像头"])


# ============== 接收推流 ==============

@router.post("/push/{stream_id}")
async def push_frame(stream_id: str, request: Request):
    """
    接收摄像头推送的图片
    
    摄像头配置:
    - 服务器地址: http://你的域名/camera/push/camera1
    - 摄像头会POST JPEG图片到此地址
    """
    frame_data = await request.body()
    if not frame_data:
        raise HTTPException(status_code=400, detail="无图片数据")
    
    stream_receiver.receive_frame(stream_id, frame_data)
    return {"success": True}


@router.api_route("/{stream_id}/{path:path}", methods=["GET", "POST", "PUT", "PATCH"])
async def camera_wildcard(stream_id: str, path: str, request: Request):
    """
    通配路由 - 适配不同摄像头协议
    摄像头配置: http://服务器/camera/摄像头ID
    """
    import logging
    logger = logging.getLogger(__name__)
    
    content_type = request.headers.get("content-type", "")
    body = await request.body()
    
    # 打印请求内容用于调试
    if "json" in content_type:
        try:
            import json
            data = json.loads(body)
            logger.info(f"[{stream_id}] {request.method} /{path} JSON: {data}")
        except:
            logger.info(f"[{stream_id}] {request.method} /{path} Body: {body[:200]}")
    else:
        logger.info(f"[{stream_id}] {request.method} /{path} Content-Type: {content_type} Size: {len(body)} bytes")
    
    # 如果是图片数据，保存帧
    if body and ("image" in content_type or len(body) > 10000):
        stream_receiver.receive_frame(stream_id, body)
        return {"success": True}
    
    # 其他请求（心跳等）返回成功
    return {"success": True}


# ============== 查看视频流 ==============

@router.get("/view/{stream_id}")
async def view_stream(stream_id: str):
    """
    查看摄像头视频流 (MJPEG格式)
    
    前端使用:
    <img src="http://你的域名/camera/view/camera1">
    """
    if stream_id not in stream_receiver.streams:
        raise HTTPException(status_code=404, detail=f"摄像头 {stream_id} 不存在或未推流")
    
    return StreamingResponse(
        stream_receiver.generate_mjpeg(stream_id),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@router.get("/snapshot/{stream_id}")
async def get_snapshot(stream_id: str):
    """获取摄像头快照 (单张JPEG图片)"""
    frame = stream_receiver.get_frame(stream_id)
    if frame:
        return Response(content=frame, media_type="image/jpeg")
    raise HTTPException(status_code=404, detail=f"摄像头 {stream_id} 无可用图片")


# ============== 管理接口 ==============

@router.get("/list")
async def list_streams():
    """列出所有摄像头"""
    return {"success": True, "data": stream_receiver.list_streams()}


@router.get("/status/{stream_id}")
async def get_stream_status(stream_id: str):
    """获取摄像头状态"""
    status = stream_receiver.get_status(stream_id)
    if status:
        return {"success": True, "data": status}
    return {"success": False, "message": f"摄像头 {stream_id} 不存在"}


@router.delete("/remove/{stream_id}")
async def remove_stream(stream_id: str):
    """移除摄像头"""
    if stream_receiver.remove_stream(stream_id):
        return {"success": True, "message": f"摄像头 {stream_id} 已移除"}
    return {"success": False, "message": f"摄像头 {stream_id} 不存在"}
