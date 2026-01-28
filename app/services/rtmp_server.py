"""
SRS 截图服务模块
从 SRS 服务器定时获取 RTMP 流截图
"""
import logging
import subprocess
import threading
import time
import httpx
from typing import Dict, Optional, List
from dataclasses import dataclass

from ..core.ffmpeg import get_ffmpeg_cmd
from ..core.config import SRS_CONFIG

logger = logging.getLogger(__name__)

# SRS 服务器配置
SRS_RTMP_URL = SRS_CONFIG["rtmp_url"]
SRS_API_URL = SRS_CONFIG["api_url"]
# 截图缓存
_snapshots: Dict[str, 'StreamSnapshot'] = {}


@dataclass
class StreamSnapshot:
    """流截图信息"""
    stream_key: str
    last_frame: Optional[bytes] = None
    last_update: float = 0
    capture_count: int = 0
    _running: bool = False


class SnapshotService:
    """SRS 截图服务"""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._running = False
        logger.info("SRS截图服务初始化完成")
    
    @property
    def streams(self) -> Dict[str, StreamSnapshot]:
        return _snapshots
    
    def register_stream(self, stream_key: str) -> bool:
        """注册一个流(开始定时截图)"""
        if stream_key in _snapshots:
            return False
        
        _snapshots[stream_key] = StreamSnapshot(
            stream_key=stream_key,
            last_update=time.time()
        )
        _snapshots[stream_key]._running = True
        
        # 启动截图线程
        threading.Thread(
            target=self._capture_loop,
            args=(stream_key,),
            daemon=True
        ).start()
        
        logger.info(f"[{stream_key}] 开始定时截图")
        return True
    
    def _capture_loop(self, stream_key: str):
        """截图循环"""
        snapshot = _snapshots.get(stream_key)
        if not snapshot:
            return
        
        ffmpeg_cmd = get_ffmpeg_cmd()
        if not ffmpeg_cmd:
            logger.error("ffmpeg不可用")
            return
        
        rtmp_url = f"{SRS_RTMP_URL}/{stream_key}"
        fail_count = 0
        
        while snapshot._running:
            try:
                # 使用 ffmpeg 从 RTMP 流截取一帧
                cmd = [
                    ffmpeg_cmd,
                    '-y',
                    '-i', rtmp_url,
                    '-vframes', '1',
                    '-f', 'image2pipe',
                    '-vcodec', 'mjpeg',
                    '-q:v', '3',
                    'pipe:1'
                ]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=5
                )
                
                if result.returncode == 0 and result.stdout:
                    snapshot.last_frame = result.stdout
                    snapshot.last_update = time.time()
                    snapshot.capture_count += 1
                    fail_count = 0
                    
                    if snapshot.capture_count % 100 == 0:
                        logger.info(f"[{stream_key}] 已截图 {snapshot.capture_count} 次")
                else:
                    fail_count += 1
                    if fail_count <= 3:
                        logger.warning(f"[{stream_key}] 截图失败: {result.stderr.decode()[:100]}")
                
            except subprocess.TimeoutExpired:
                fail_count += 1
                if fail_count <= 3:
                    logger.warning(f"[{stream_key}] 截图超时")
            except Exception as e:
                fail_count += 1
                if fail_count <= 3:
                    logger.error(f"[{stream_key}] 截图异常: {e}")
            
            # 每秒截图一次
            time.sleep(1)
    
    def get_frame(self, stream_key: str) -> Optional[bytes]:
        """获取最新截图"""
        # 自动注册流
        if stream_key not in _snapshots:
            self.register_stream(stream_key)
            # 等待首次截图
            for _ in range(30):  # 最多等待3秒
                time.sleep(0.1)
                if _snapshots.get(stream_key) and _snapshots[stream_key].last_frame:
                    break
        
        snapshot = _snapshots.get(stream_key)
        return snapshot.last_frame if snapshot else None
    
    def get_status(self, stream_key: str) -> Optional[dict]:
        """获取流状态"""
        snapshot = _snapshots.get(stream_key)
        if not snapshot:
            return None
        
        from datetime import datetime
        is_online = (time.time() - snapshot.last_update) < 10 if snapshot.last_update else False
        
        return {
            "stream_key": snapshot.stream_key,
            "capture_count": snapshot.capture_count,
            "is_online": is_online,
            "last_update": datetime.fromtimestamp(snapshot.last_update).isoformat() if snapshot.last_update else None,
        }
    
    def list_streams(self) -> list:
        """列出所有已注册的流(截图服务)"""
        return [self.get_status(key) for key in _snapshots.keys()]
    
    def list_srs_streams(self) -> List[dict]:
        """从SRS获取当前在线的流列表"""
        try:
            # SRS API 需要尾部斜杠，否则返回 302
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
                        "has_snapshot": s.get("name") in _snapshots,
                    })
                return streams
            else:
                logger.warning(f"获取SRS流列表失败: HTTP {resp.status_code}")
        except Exception as e:
            logger.warning(f"获取SRS流列表失败: {e}")
        return []
    
    def remove_stream(self, stream_key: str) -> bool:
        """移除流"""
        if stream_key in _snapshots:
            _snapshots[stream_key]._running = False
            del _snapshots[stream_key]
            logger.info(f"[{stream_key}] 已移除")
            return True
        return False
    
    def stop(self):
        """停止所有截图"""
        self._running = False
        for key in list(_snapshots.keys()):
            _snapshots[key]._running = False
        _snapshots.clear()
        logger.info("SRS截图服务已停止")


# 全局实例（保持兼容性）
rtmp_server = SnapshotService()
