"""实验相关路由"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
import httpx
import json

from ..core import SSH_CONFIG, API_PATHS, BASE_HEADERS, get_tunnel
from ..schemas import (
    LoginRequest, AuthRequest, ExperimentListRequest,
    CreateExperimentRequest, StartExperimentRequest, DeleteExperimentRequest
)

router = APIRouter(prefix="/target", tags=["实验"])


def _get_base_url():
    return f"http://127.0.0.1:{SSH_CONFIG['local_port']}"


@router.post("/login")
async def login(req: LoginRequest):
    """登录"""
    try:
        get_tunnel()
        headers = {**BASE_HEADERS, "content-type": "application/json;charset=UTF-8"}
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{_get_base_url()}/{API_PATHS['login']}",
                json=req.model_dump(),
                headers=headers,
            )
            return Response(content=response.content, status_code=response.status_code, media_type="application/json")
    
    except httpx.ConnectError as e:
        raise HTTPException(status_code=502, detail=f"无法连接到内网服务: {e}")


@router.post("/get_experiments")
async def get_experiments(req: ExperimentListRequest):
    """获取实验列表"""
    try:
        get_tunnel()
        headers = {**BASE_HEADERS, "authorization": req.authorization}
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                f"{_get_base_url()}/{API_PATHS['experiment_list']}",
                params={"pageNum": req.pageNum, "pageSize": req.pageSize},
                headers=headers,
            )
            return Response(content=response.content, status_code=response.status_code, media_type="application/json")
    
    except httpx.ConnectError as e:
        raise HTTPException(status_code=502, detail=f"无法连接到内网服务: {e}")


@router.post("/experimentInstance/generateExperimentCode")
async def generate_code(req: AuthRequest):
    """生成实验编号"""
    try:
        get_tunnel()
        headers = {**BASE_HEADERS, "authorization": req.authorization}
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                f"{_get_base_url()}/{API_PATHS['generate_code']}",
                headers=headers,
            )
            return Response(content=response.content, status_code=response.status_code, media_type="application/json")
    
    except httpx.ConnectError as e:
        raise HTTPException(status_code=502, detail=f"无法连接到内网服务: {e}")


@router.post("/start-experiment")
async def start_experiment(req: StartExperimentRequest):
    """启动实验"""
    try:
        get_tunnel()
        headers = {**BASE_HEADERS, "authorization": req.authorization, "content-type": "application/json;charset=UTF-8"}
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            # 获取实验列表
            list_resp = await client.get(
                f"{_get_base_url()}/{API_PATHS['experiment_list']}",
                params={"pageNum": 1, "pageSize": 100},
                headers=headers,
            )
            data = list_resp.json()
            
            # 查找目标实验
            items = data.get("data", {})
            if isinstance(items, dict):
                items = items.get("list", [])
            
            target = next((i for i in items if i.get("experienceCode") == req.exp_code), None)
            if not target:
                raise HTTPException(status_code=404, detail=f"未找到实验: {req.exp_code}")
            
            # 启动实验
            response = await client.post(
                f"{_get_base_url()}/{API_PATHS['start_experiment']}",
                json=target,
                headers=headers,
            )
            return Response(content=response.content, status_code=response.status_code, media_type="application/json")
    
    except HTTPException:
        raise
    except httpx.ConnectError as e:
        raise HTTPException(status_code=502, detail=f"无法连接到内网服务: {e}")


@router.post("/mock/start-experiment")
async def mock_start_experiment(req: StartExperimentRequest):
    """（Mock）启动实验：返回匹配的实验 item，不真正触发启动"""
    try:
        get_tunnel()
        headers = {**BASE_HEADERS, "authorization": req.authorization, "content-type": "application/json;charset=UTF-8"}

        async with httpx.AsyncClient(timeout=60.0) as client:
            # 获取实验列表
            list_resp = await client.get(
                f"{_get_base_url()}/{API_PATHS['experiment_list']}",
                params={"pageNum": 1, "pageSize": 100},
                headers=headers,
            )
            data = list_resp.json()

            # 查找目标实验
            items = data.get("data", {})
            if isinstance(items, dict):
                items = items.get("list", [])

            target = next((i for i in items if i.get("experienceCode") == req.exp_code), None)
            if not target:
                raise HTTPException(status_code=404, detail=f"未找到实验: {req.exp_code}")

            # 启动实验（mock 版不执行）
            # response = await client.post(
            #     f"{_get_base_url()}/{API_PATHS['start_experiment']}",
            #     json=target,
            #     headers=headers,
            # )
            # return Response(content=response.content, status_code=response.status_code, media_type="application/json")

            return Response(content=json.dumps(target, ensure_ascii=False), status_code=200, media_type="application/json")

    except HTTPException:
        raise
    except httpx.ConnectError as e:
        raise HTTPException(status_code=502, detail=f"无法连接到内网服务: {e}")


@router.post("/delete-experiment")
async def delete_experiment(req: DeleteExperimentRequest):
    """删除实验"""
    try:
        get_tunnel()
        headers = {**BASE_HEADERS, "authorization": req.authorization}
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.delete(
                f"{_get_base_url()}/{API_PATHS['delete_experiment']}/{req.id}",
                headers=headers,
            )
            return Response(content=response.content, status_code=response.status_code, media_type="application/json")
    
    except httpx.ConnectError as e:
        raise HTTPException(status_code=502, detail=f"无法连接到内网服务: {e}")


@router.post("/create-targeted-experiment")
async def create_experiment(req: CreateExperimentRequest):
    """创建实验"""
    try:
        get_tunnel()
        headers = {**BASE_HEADERS, "authorization": req.authorization, "content-type": "application/json;charset=UTF-8"}
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            # 获取实验编号
            code_resp = await client.get(f"{_get_base_url()}/{API_PATHS['generate_code']}", headers=headers)
            code_data = code_resp.json()
            if not code_data.get("success"):
                raise HTTPException(status_code=500, detail=f"获取实验编号失败: {code_data.get('message')}")
            
            # 创建实验
            payload = {
                "experimentId": 64,
                "experienceCode": code_data["data"],
                "isDynamic": 1,
                "samplePlateIdList": [],
                "variableList": [{"variableId": 40, "value": "5", "name": "Loop_AGV", "tasknodeProcessId": 40}],
                "name": req.name,
                "loopCount": 1,
                "priority": 2,
                "startMethod": 1,
            }
            response = await client.post(f"{_get_base_url()}/{API_PATHS['create_instance']}", json=payload, headers=headers)
            return Response(content=response.content, status_code=response.status_code, media_type="application/json")
    
    except HTTPException:
        raise
    except httpx.ConnectError as e:
        raise HTTPException(status_code=502, detail=f"无法连接到内网服务: {e}")
