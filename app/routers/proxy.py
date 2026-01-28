"""通用代理路由"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response
import httpx

from ..core import SSH_CONFIG, get_tunnel

router = APIRouter(prefix="/proxy", tags=["代理"])


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_request(path: str, request: Request):
    """通用请求代理"""
    try:
        get_tunnel()
        target_url = f"http://127.0.0.1:{SSH_CONFIG['local_port']}/{path}"
        
        headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in ["host", "content-length", "transfer-encoding"]
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.request(
                method=request.method,
                url=target_url,
                params=dict(request.query_params),
                content=await request.body() or None,
                headers=headers,
            )
            
            response_headers = {
                k: v for k, v in response.headers.items()
                if k.lower() not in ["content-encoding", "transfer-encoding", "content-length"]
            }
            
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=response_headers,
                media_type=response.headers.get("content-type", "application/octet-stream"),
            )
    
    except httpx.ConnectError as e:
        raise HTTPException(status_code=502, detail=f"无法连接到内网服务: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"代理错误: {e}")
