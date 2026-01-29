"""
RTMP 视频流路由
RTMP 由 SRS Docker 处理
"""
import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..services.rtmp_server import rtmp_server
from ..core.config import SRS_CONFIG

router = APIRouter(prefix="/rtmp", tags=["RTMP视频流"])

SRS_HTTP_URL = SRS_CONFIG["http_url"]


@router.get("/list")
async def list_streams():
    """列出所有在线的 RTMP 流"""
    return {"success": True, "data": rtmp_server.list_streams()}


@router.get("/play/{stream_key}.flv")
async def play_flv(stream_key: str):
    """
    代理 HTTP-FLV 流
    
    前端使用: /rtmp/play/camera1.flv
    """
    url = f"{SRS_HTTP_URL}/live/{stream_key}.flv"
    
    async def stream_proxy():
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", url, timeout=None) as resp:
                if resp.status_code != 200:
                    raise HTTPException(status_code=resp.status_code, detail="流不存在")
                async for chunk in resp.aiter_bytes(chunk_size=4096):
                    yield chunk
    
    return StreamingResponse(
        stream_proxy(),
        media_type="video/x-flv",
        headers={"Cache-Control": "no-cache"}
    )


@router.get("/play/{stream_key}.m3u8")
async def play_hls(stream_key: str):
    """
    代理 HLS m3u8
    
    前端使用: /rtmp/play/camera1.m3u8
    """
    url = f"{SRS_HTTP_URL}/live/{stream_key}.m3u8"
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=5)
        if resp.status_code != 200:
            raise HTTPException(status_code=404, detail="流不存在")
        return StreamingResponse(
            iter([resp.content]),
            media_type="application/vnd.apple.mpegurl"
        )


@router.get("/play/{path:path}")
async def play_ts(path: str):
    """代理 HLS ts 分片"""
    url = f"{SRS_HTTP_URL}/live/{path}"
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=10)
        if resp.status_code != 200:
            raise HTTPException(status_code=404, detail="分片不存在")
        return StreamingResponse(
            iter([resp.content]),
            media_type="video/mp2t"
        )
