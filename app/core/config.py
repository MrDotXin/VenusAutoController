"""应用配置"""
import os
from dotenv import load_dotenv

load_dotenv()

# SSH配置
SSH_CONFIG = {
    "host": os.getenv("SSH_HOST", "ip2"),
    "port": int(os.getenv("SSH_PORT", 8130)),
    "username": os.getenv("SSH_USERNAME", "venus"),
    "password": os.getenv("SSH_PASSWORD", ""),
    "remote_host": os.getenv("REMOTE_HOST", "ip1"),
    "remote_port": int(os.getenv("REMOTE_PORT", 80)),
    "local_port": int(os.getenv("LOCAL_PORT", 8000)),
}

# 目标服务API路径
API_PATHS = {
    "login": "api/userAccount/userAccountLogin",
    "experiment_list": "api/experimentInstance/findExperimentInstanceList",
    "generate_code": "api/experimentInstance/generateExperimentCode",
    "create_instance": "api/instance/add",
    "start_experiment": "api/experimentInstance/startInstance",
    "delete_experiment": "api/experimentInstance/deleteExperimentInstance",
}

# 请求头
BASE_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "appid": "api-server",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}

# SRS流媒体服务器配置
SRS_CONFIG = {
    "rtmp_url": os.getenv("SRS_RTMP_URL", "rtmp://localhost:1935/live"),
    "api_url": os.getenv("SRS_API_URL", "http://localhost:5002"),
}
