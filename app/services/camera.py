"""
摄像头HTTP推流接收模块
摄像头通过HTTP POST推送图片到服务器
"""
import asyncio
import time
import logging
import threading
from typing import Optional, Dict, Generator, AsyncGenerator
from dataclasses import dataclass, field
from collections import deque
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class StreamInfo:
    """流信息"""
    stream_id: str
    frame_count: int = 0
    last_update: float = 0
    last_frame: Optional[bytes] = None
    _frame_buffer: deque = field(default_factory=lambda: deque(maxlen=30))


class HTTPStreamReceiver:
    """
    HTTP流接收器
    接收摄像头通过HTTP POST推送的图片帧
    """
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
        self.streams: Dict[str, StreamInfo] = {}
        self._lock = threading.Lock()
        logger.info("HTTP流接收器初始化完成")
    
    def receive_frame(self, stream_id: str, frame_data: bytes) -> bool:
        """
        接收一帧图片数据
        摄像头POST数据到此方法
        """
        with self._lock:
            is_new = stream_id not in self.streams
            if is_new:
                self.streams[stream_id] = StreamInfo(stream_id=stream_id)
                logger.info(f"新摄像头连接: {stream_id}")
            
            stream = self.streams[stream_id]
            stream.last_frame = frame_data
            stream._frame_buffer.append(frame_data)
            stream.frame_count += 1
            stream.last_update = time.time()
            
            # 每100帧输出一次统计日志
            if stream.frame_count % 100 == 0:
                logger.info(f"[{stream_id}] 已接收 {stream.frame_count} 帧, 当前帧大小: {len(frame_data)} bytes")
            
        return True
    
    def get_frame(self, stream_id: str) -> Optional[bytes]:
        """获取最新帧"""
        stream = self.streams.get(stream_id)
        if stream:
            return stream.last_frame
        return None
    
    async def generate_mjpeg(self, stream_id: str) -> AsyncGenerator[bytes, None]:
        """
        生成MJPEG视频流（异步）
        前端可用 <img src="..."> 直接显示
        """
        last_frame = None
        no_frame_count = 0
        while True:
            stream = self.streams.get(stream_id)
            if not stream:
                break
            
            if stream.last_frame:
                no_frame_count = 0
                if stream.last_frame != last_frame:
                    last_frame = stream.last_frame
                    yield (
                        b'--frame\r\n'
                        b'Content-Type: image/jpeg\r\n\r\n' +
                        stream.last_frame +
                        b'\r\n'
                    )
            else:
                no_frame_count += 1
                if no_frame_count > 600:  # 30秒无数据退出
                    break
            
            await asyncio.sleep(0.05)  # 20fps
    
    def get_status(self, stream_id: str) -> Optional[dict]:
        """获取流状态"""
        stream = self.streams.get(stream_id)
        if not stream:
            return None
        
        # 检查是否在线（30秒内有更新）
        is_online = (time.time() - stream.last_update) < 30 if stream.last_update else False
        
        return {
            "stream_id": stream.stream_id,
            "frame_count": stream.frame_count,
            "is_online": is_online,
            "last_update": datetime.fromtimestamp(stream.last_update).isoformat() if stream.last_update else None,
        }
    
    def list_streams(self) -> list:
        """列出所有流"""
        return [self.get_status(sid) for sid in self.streams.keys()]
    
    def remove_stream(self, stream_id: str) -> bool:
        """移除流"""
        with self._lock:
            if stream_id in self.streams:
                del self.streams[stream_id]
                logger.info(f"移除流: {stream_id}")
                return True
        return False


# 全局实例
stream_receiver = HTTPStreamReceiver()
