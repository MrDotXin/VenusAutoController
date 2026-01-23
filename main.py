"""
SSH隧道代理服务
通过SSH隧道转发请求到内网接口，支持UI界面和静态资源
"""
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from sshtunnel import SSHTunnelForwarder
from contextlib import asynccontextmanager
import httpx
import os
from dotenv import load_dotenv
import threading
import time
import logging

load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 全局隧道实例
_tunnel_instance = None
_tunnel_lock = threading.Lock()
_heartbeat_thread = None
_heartbeat_running = False


def heartbeat_monitor():
    """心跳监控线程，定期检查并维持SSH连接"""
    global _tunnel_instance, _heartbeat_running
    
    while _heartbeat_running:
        try:
            with _tunnel_lock:
                if _tunnel_instance is not None:
                    if not _tunnel_instance.is_active:
                        logger.warning("检测到SSH隧道断开，尝试重连...")
                        try:
                            _tunnel_instance.stop()
                        except Exception:
                            pass
                        _tunnel_instance = None
                        # 触发重连
                        create_tunnel()
                        logger.info("SSH隧道重连成功")
                    else:
                        # 连接正常，记录心跳
                        logger.debug("SSH隧道心跳正常")
        except Exception as e:
            logger.error(f"心跳检测异常: {e}")
        
        # 每15秒检查一次
        time.sleep(15)


def start_heartbeat():
    """启动心跳监控线程"""
    global _heartbeat_thread, _heartbeat_running
    _heartbeat_running = True
    _heartbeat_thread = threading.Thread(target=heartbeat_monitor, daemon=True)
    _heartbeat_thread.start()
    logger.info("心跳监控线程已启动")


def stop_heartbeat():
    """停止心跳监控线程"""
    global _heartbeat_running
    _heartbeat_running = False
    logger.info("心跳监控线程已停止")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global _tunnel_instance
    # 启动时建立SSH隧道
    try:
        _tunnel_instance = get_tunnel()
        start_heartbeat()
        logger.info("SSH隧道已建立")
    except Exception as e:
        logger.error(f"SSH隧道建立失败: {e}")
    
    yield
    
    # 关闭时停止心跳并断开SSH隧道
    stop_heartbeat()
    if _tunnel_instance:
        _tunnel_instance.stop()
        logger.info("SSH隧道已关闭")


app = FastAPI(title="SSH Proxy Server", description="SSH隧道代理服务", lifespan=lifespan)

# CORS配置，允许React前端调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境请限制为具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SSH配置（从环境变量读取）
SSH_CONFIG = {
    "host": os.getenv("SSH_HOST", "ip2"),
    "port": int(os.getenv("SSH_PORT", 8130)),
    "username": os.getenv("SSH_USERNAME", "venus"),
    "password": os.getenv("SSH_PASSWORD", ""),
    "remote_host": os.getenv("REMOTE_HOST", "ip1"),
    "remote_port": int(os.getenv("REMOTE_PORT", 80)),
    "local_port": int(os.getenv("LOCAL_PORT", 8000)),
}

def create_tunnel():
    """创建新的SSH隧道"""
    global _tunnel_instance
    _tunnel_instance = SSHTunnelForwarder(
        (SSH_CONFIG["host"], SSH_CONFIG["port"]),
        ssh_username=SSH_CONFIG["username"],
        ssh_password=SSH_CONFIG["password"],
        remote_bind_address=(SSH_CONFIG["remote_host"], SSH_CONFIG["remote_port"]),
        local_bind_address=("127.0.0.1", SSH_CONFIG["local_port"]),
        set_keepalive=30,  # 每30秒发送SSH心跳包
        allow_agent=False,  # 跳过SSH agent
        ssh_pkey=None,  # 不使用私钥文件
    )
    _tunnel_instance.start()
    return _tunnel_instance


def get_tunnel():
    """获取或创建SSH隧道单例"""
    global _tunnel_instance
    with _tunnel_lock:
        if _tunnel_instance is None or not _tunnel_instance.is_active:
            if _tunnel_instance is not None:
                logger.warning("SSH隧道已断开，正在重连...")
                try:
                    _tunnel_instance.stop()
                except Exception:
                    pass
            create_tunnel()
            logger.info("SSH隧道已建立/重连成功")
        return _tunnel_instance


# 目标服务接口路径配置
LOGIN_PATH = "api/userAccount/userAccountLogin"
EXPERIMENT_LIST_PATH = "api/experimentInstance/findExperimentInstanceList"
GENERATE_EXP_CODE_PATH = "api/experimentInstance/generateExperimentCode"
CREATE_INSTANCE_PATH = "api/instance/add"
START_EXPERIMENT_PATH = "api/experimentInstance/startInstance"
BASE_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "appid": "api-server",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
}


from pydantic import BaseModel

class LoginRequest(BaseModel):
    accountName: str
    accountPwd: str


class ExperimentListRequest(BaseModel):
    authorization: str
    pageNum: int = 1
    pageSize: int = 10


class AuthRequest(BaseModel):
    authorization: str


class CreateExperimentRequest(BaseModel):
    authorization: str
    name: str  # 实验名称


class StartExperimentRequest(BaseModel):
    authorization: str
    exp_code: str  # 实验编号


@app.post("/target/login")
async def target_login(login_data: LoginRequest):
    """
    登录接口转发
    访问: POST http://localhost:5000/target/login
    Body: {"accountName": "xxx", "accountPwd": "xxx"}
    转发到: 目标服务 /api/userAccount/userAccountLogin
    """
    try:
        get_tunnel()
        
        target_url = f"http://127.0.0.1:{SSH_CONFIG['local_port']}/{LOGIN_PATH}"
        
        headers = BASE_HEADERS.copy()
        headers["content-type"] = "application/json;charset=UTF-8"
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url=target_url,
                json=login_data.model_dump(),
                headers=headers,
            )
            
            # 返回原始响应
            return Response(
                content=response.content,
                status_code=response.status_code,
                media_type="application/json",
            )
    
    except httpx.ConnectError as e:
        raise HTTPException(status_code=502, detail=f"无法连接到内网服务: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"登录代理错误: {str(e)}")


@app.post("/target/get_experiments")
async def get_experiments(req: ExperimentListRequest):
    """
    获取实验实例列表
    访问: POST http://localhost:5000/target/get_experiments
    Body: {"authorization": "token", "pageNum": 1, "pageSize": 10}
    转发到: 目标服务 /api/experimentInstance/findExperimentInstanceList
    """
    try:
        get_tunnel()
        
        target_url = f"http://127.0.0.1:{SSH_CONFIG['local_port']}/{EXPERIMENT_LIST_PATH}"
        
        headers = BASE_HEADERS.copy()
        headers["authorization"] = req.authorization
        
        params = {
            "pageNum": req.pageNum,
            "pageSize": req.pageSize
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                url=target_url,
                params=params,
                headers=headers,
            )
            
            return Response(
                content=response.content,
                status_code=response.status_code,
                media_type="application/json",
            )
    
    except httpx.ConnectError as e:
        raise HTTPException(status_code=502, detail=f"无法连接到内网服务: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取实验列表错误: {str(e)}")


@app.post("/target/mock/start-experiment")
async def start_experiment(req: StartExperimentRequest):
    """
    启动实验实例
    访问: POST http://localhost:5000/target/start-experiment
    Body: {"authorization": "token", "exp_code": "EXP202601230017"}
    流程: 1. 获取实验列表 -> 2. 匹配 exp_code -> 3. 启动实验
    """
    try:
        get_tunnel()
        
        headers = BASE_HEADERS.copy()
        headers["authorization"] = req.authorization
        headers["content-type"] = "application/json;charset=UTF-8"
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            # 步骤1: 获取实验列表
            list_url = f"http://127.0.0.1:{SSH_CONFIG['local_port']}/{EXPERIMENT_LIST_PATH}"
            list_response = await client.get(
                url=list_url,
                params={"pageNum": 1, "pageSize": 100},
                headers=headers,
            )
            list_response.raise_for_status()
            
            data = list_response.json()
            
            # 提取列表数据
            items = []
            if isinstance(data, dict) and "data" in data:
                if isinstance(data["data"], list):
                    items = data["data"]
                elif isinstance(data["data"], dict) and "list" in data["data"]:
                    items = data["data"]["list"]
            
            # 步骤2: 匹配 exp_code
            target_item = None
            for item in items:
                if item.get("experienceCode") == req.exp_code:
                    target_item = item
                    break
            
            if not target_item:
                raise HTTPException(status_code=404, detail=f"未找到实验编号: {req.exp_code}")
            
            print(target_item)            
            # 步骤3: 启动实验
            # start_url = f"http://127.0.0.1:{SSH_CONFIG['local_port']}/{START_EXPERIMENT_PATH}"
            # start_response = await client.post(
            #     url=start_url,
            #     json=target_item,
            #     headers=headers,
            # )
            print("模拟发送接口!")
            
            return Response(
                content='ok',#start_response.content,
                status_code=200,#start_response.status_code,
                media_type="application/json",
            )
    
    except httpx.ConnectError as e:
        raise HTTPException(status_code=502, detail=f"无法连接到内网服务: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动实验错误: {str(e)}")

@app.post("/target/start-experiment")
async def start_experiment(req: StartExperimentRequest):
    """
    启动实验实例
    访问: POST http://localhost:5000/target/start-experiment
    Body: {"authorization": "token", "exp_code": "EXP202601230017"}
    流程: 1. 获取实验列表 -> 2. 匹配 exp_code -> 3. 启动实验
    """
    try:
        get_tunnel()
        
        headers = BASE_HEADERS.copy()
        headers["authorization"] = req.authorization
        headers["content-type"] = "application/json;charset=UTF-8"
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            # 步骤1: 获取实验列表
            list_url = f"http://127.0.0.1:{SSH_CONFIG['local_port']}/{EXPERIMENT_LIST_PATH}"
            list_response = await client.get(
                url=list_url,
                params={"pageNum": 1, "pageSize": 100},
                headers=headers,
            )
            list_response.raise_for_status()
            
            data = list_response.json()
            
            # 提取列表数据
            items = []
            if isinstance(data, dict) and "data" in data:
                if isinstance(data["data"], list):
                    items = data["data"]
                elif isinstance(data["data"], dict) and "list" in data["data"]:
                    items = data["data"]["list"]
            
            # 步骤2: 匹配 exp_code
            target_item = None
            for item in items:
                if item.get("experienceCode") == req.exp_code:
                    target_item = item
                    break
            
            if not target_item:
                raise HTTPException(status_code=404, detail=f"未找到实验编号: {req.exp_code}")
            
            print(target_item)            
            # 步骤3: 启动实验
            start_url = f"http://127.0.0.1:{SSH_CONFIG['local_port']}/{START_EXPERIMENT_PATH}"
            start_response = await client.post(
                url=start_url,
                json=target_item,
                headers=headers,
            )
            
            return Response(
                content=start_response.content,
                status_code=start_response.status_code,
                media_type="application/json",
            )
    
    except httpx.ConnectError as e:
        raise HTTPException(status_code=502, detail=f"无法连接到内网服务: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动实验错误: {str(e)}")


@app.post("/target/experimentInstance/generateExperimentCode")
async def generate_experiment_code(req: AuthRequest):
    """
    生成实验编号
    访问: POST http://localhost:5000/target/experimentInstance/generateExperimentCode
    Body: {"authorization": "token"}
    转发到: /api/experimentInstance/generateExperimentCode
    """
    try:
        get_tunnel()
        
        target_url = f"http://127.0.0.1:{SSH_CONFIG['local_port']}/{GENERATE_EXP_CODE_PATH}"
        
        headers = BASE_HEADERS.copy()
        headers["authorization"] = req.authorization
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                url=target_url,
                headers=headers,
            )
            
            return Response(
                content=response.content,
                status_code=response.status_code,
                media_type="application/json",
            )
    
    except httpx.ConnectError as e:
        raise HTTPException(status_code=502, detail=f"无法连接到内网服务: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成实验编号错误: {str(e)}")


@app.post("/target/create-targeted-experiment")
async def create_targeted_experiment(req: CreateExperimentRequest):
    """
    创建目标实验
    访问: POST http://localhost:5000/target/create-targeted-experiment
    Body: {"authorization": "token", "name": "实验名称"}
    流程: 1. 获取实验编号 -> 2. 创建实验实例
    """
    try:
        get_tunnel()
        
        headers = BASE_HEADERS.copy()
        headers["authorization"] = req.authorization
        headers["content-type"] = "application/json;charset=UTF-8"
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            # 步骤1: 获取实验编号
            code_url = f"http://127.0.0.1:{SSH_CONFIG['local_port']}/{GENERATE_EXP_CODE_PATH}"
            code_response = await client.get(url=code_url, headers=headers)
            code_response.raise_for_status()
            
            code_data = code_response.json()
            if not code_data.get("success"):
                raise HTTPException(status_code=500, detail=f"获取实验编号失败: {code_data.get('message')}")
            
            exp_code = code_data["data"]
            
            # 步骤2: 创建实验实例
            create_url = f"http://127.0.0.1:{SSH_CONFIG['local_port']}/{CREATE_INSTANCE_PATH}"
            payload = {
                "samplePlateCsvFileName": None,
                "experimentId": 64,
                "experienceCode": exp_code,
                "isDynamic": 1,
                "samplePlateIdList": [],
                "variableList": [
                    {
                        "variableId": 40,
                        "value": "5",
                        "name": "Loop_AGV",
                        "tasknodeProcessId": 40,
                        "wfProcessId": None
                    }
                ],
                "samplePlateCsvFileUrl": "",
                "name": req.name,
                "loopCount": 1,
                "priority": 2,
                "startMethod": 1
            }
            
            create_response = await client.post(
                url=create_url,
                json=payload,
                headers=headers,
            )
            
            return Response(
                content=create_response.content,
                status_code=create_response.status_code,
                media_type="application/json",
            )
    
    except httpx.ConnectError as e:
        raise HTTPException(status_code=502, detail=f"无法连接到内网服务: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建实验错误: {str(e)}")


@app.api_route("/proxy/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_with_prefix(path: str, request: Request):
    """
    /proxy 前缀的请求转发
    访问: http://localhost:5000/proxy/iMagicOS-control/control
    """
    return await proxy_request_internal(path, request)


async def proxy_request_internal(path: str, request: Request):
    """
    代理所有请求到内网接口
    """
    try:
        # 确保隧道存在
        get_tunnel()
        
        # 构建目标URL
        target_url = f"http://127.0.0.1:{SSH_CONFIG['local_port']}/{path}"
        
        # 获取查询参数
        query_params = dict(request.query_params)
        
        # 获取请求体
        body = await request.body()
        
        # 获取请求头（排除host相关）
        headers = {
            k: v for k, v in request.headers.items() 
            if k.lower() not in ["host", "content-length", "transfer-encoding"]
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.request(
                method=request.method,
                url=target_url,
                params=query_params,
                content=body if body else None,
                headers=headers,
            )
            
            # 获取响应的Content-Type
            content_type = response.headers.get("content-type", "application/octet-stream")
            
            # 构建响应头（排除某些头）
            response_headers = {
                k: v for k, v in response.headers.items()
                if k.lower() not in ["content-encoding", "transfer-encoding", "content-length"]
            }
            
            # 直接返回JSON响应
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=response_headers,
                media_type=content_type,
            )
    
    except httpx.ConnectError as e:
        raise HTTPException(status_code=502, detail=f"无法连接到内网服务: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"代理错误: {str(e)}")



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
