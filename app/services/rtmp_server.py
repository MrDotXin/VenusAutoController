"""
SRS 流媒体服务模块
查询 SRS 在线流列表
"""
import logging
import httpx
from typing import List

from ..core.config import SRS_CONFIG

logger = logging.getLogger(__name__)

SRS_API_URL = SRS_CONFIG["api_url"]


class SRSService:
    """SRS 服务"""
    
    def list_streams(self) -> List[dict]:
        """从 SRS 获取当前在线的流列表"""
        try:
            resp = httpx.get(f"{SRS_API_URL}/api/v1/streams/", timeout=3, follow_redirects=True)
            if resp.status_code == 200:
                data = resp.json()
                streams = []
                for s in data.get("streams", []):
                    streams.append({
                        "stream_key": s.get("name"),
                        "app": s.get("app"),
                        "client_id": s.get("publish", {}).get("cid"),
                        "is_online": True,
                    })
                return streams
            else:
                logger.warning(f"获取SRS流列表失败: HTTP {resp.status_code}")
        except Exception as e:
            logger.warning(f"获取SRS流列表失败: {e}")
        return []
    
    def stop(self):
        """停止服务(兼容旧接口)"""
        pass


# 全局实例
rtmp_server = SRSService()
