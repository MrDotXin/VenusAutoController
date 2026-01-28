"""
RTMP服务器模块
使用pyrtmp接收摄像头RTMP推流，转码为MJPEG供前端查看
"""
import asyncio
import logging
import subprocess
import threading
import time
from typing import Dict, Optional, Generator
from dataclasses import dataclass

from pyrtmp import StreamClosedException
from pyrtmp.session_manager import SessionManager
from pyrtmp.rtmp import SimpleRTMPController
from pyrtmp.messages.video import VideoMessage
from pyrtmp.messages.command import NSPublish

logger = logging.getLogger(__name__)

# 全局流存储（跨controller共享）
_streams: Dict[str, 'RTMPStream'] = {}


@dataclass
class RTMPStream:
    """流信息"""
    stream_key: str
    app: str = "live"
    frame_count: int = 0
    packet_count: int = 0
    last_update: float = 0
    last_frame: Optional[bytes] = None
    ffmpeg_process: Optional[subprocess.Popen] = None
    _running: bool = False


class CameraRTMPController(SimpleRTMPController):
    """摄像头RTMP控制器 - 只需覆盖关心的方法"""
    
    def __init__(self):
        self.stream_key: Optional[str] = None
    
    async def on_ns_publish(self, session: SessionManager, message: NSPublish) -> None:
        """收到publish命令时创建流"""
        # 先调用父类处理协议响应
        await super().on_ns_publish(session, message)
        
        # 创建流
        app = getattr(session, '_app', 'live')
        self.stream_key = f"{app}_{message.publishing_name}_{int(time.time())}"
        logger.info(f"[RTMP] publish: {message.publishing_name} -> {self.stream_key}")
        
        _streams[self.stream_key] = RTMPStream(
            stream_key=self.stream_key,
            app=app,
            last_update=time.time()
        )
        
        # 启动ffmpeg
        _start_ffmpeg(self.stream_key)
    
    async def on_video_message(self, session: SessionManager, message: VideoMessage) -> None:
        """处理视频数据"""
        if not self.stream_key:
            return
        
        stream = _streams.get(self.stream_key)
        if not stream:
            return
        
        stream.packet_count += 1
        stream.last_update = time.time()
        
        # 写入ffmpeg
        if stream.ffmpeg_process and stream.ffmpeg_process.stdin:
            try:
                stream.ffmpeg_process.stdin.write(message.payload)
                stream.ffmpeg_process.stdin.flush()
            except:
                pass
        
        if stream.packet_count % 500 == 0:
            logger.info(f"[{self.stream_key}] 已接收 {stream.packet_count} 个视频包")
    
    async def on_stream_closed(self, session: SessionManager, exception: StreamClosedException) -> None:
        """流关闭时清理"""
        self._cleanup()
    
    async def cleanup(self, session: SessionManager) -> None:
        """连接结束时清理"""
        self._cleanup()
    
    def _cleanup(self):
        if self.stream_key:
            _stop_ffmpeg(self.stream_key)
            if self.stream_key in _streams:
                del _streams[self.stream_key]
            logger.info(f"[RTMP] 流已清理: {self.stream_key}")
            self.stream_key = None


def _start_ffmpeg(stream_key: str):
    """启动ffmpeg转码进程"""
    from ..core.ffmpeg import get_ffmpeg_cmd
    
    stream = _streams.get(stream_key)
    if not stream:
        return
    
    ffmpeg_cmd = get_ffmpeg_cmd()
    if not ffmpeg_cmd:
        logger.error("ffmpeg不可用")
        return
    
    cmd = [
        ffmpeg_cmd,
        '-f', 'h264',
        '-i', 'pipe:0',
        '-f', 'image2pipe',
        '-vcodec', 'mjpeg',
        '-q:v', '5',
        '-r', '15',
        'pipe:1'
    ]
    
    try:
        stream.ffmpeg_process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stream._running = True
        
        threading.Thread(
            target=_read_ffmpeg_output,
            args=(stream_key,),
            daemon=True
        ).start()
        
        logger.info(f"[{stream_key}] ffmpeg转码已启动")
    except Exception as e:
        logger.error(f"[{stream_key}] ffmpeg启动失败: {e}")


def _read_ffmpeg_output(stream_key: str):
    """读取ffmpeg输出的MJPEG帧"""
    stream = _streams.get(stream_key)
    if not stream or not stream.ffmpeg_process:
        return
    
    buffer = b''
    frame_count = 0
    while stream._running:
        try:
            chunk = stream.ffmpeg_process.stdout.read(4096)
            if not chunk:
                break
            
            buffer += chunk
            
            while True:
                start = buffer.find(b'\xff\xd8')
                if start == -1:
                    break
                
                end = buffer.find(b'\xff\xd9', start + 2)
                if end == -1:
                    break
                
                frame = buffer[start:end + 2]
                stream.last_frame = frame
                stream.frame_count = frame_count
                buffer = buffer[end + 2:]
                frame_count += 1
                
                if frame_count % 100 == 0:
                    logger.info(f"[{stream_key}] 已转码 {frame_count} 帧")
                
        except Exception as e:
            logger.error(f"[{stream_key}] 读取ffmpeg输出错误: {e}")
            break


def _stop_ffmpeg(stream_key: str):
    """停止ffmpeg进程"""
    stream = _streams.get(stream_key)
    if stream:
        stream._running = False
        if stream.ffmpeg_process:
            try:
                stream.ffmpeg_process.terminate()
                stream.ffmpeg_process.wait(timeout=5)
            except:
                stream.ffmpeg_process.kill()
            stream.ffmpeg_process = None
        logger.info(f"[{stream_key}] ffmpeg已停止")


class RTMPServer:
    """RTMP服务器"""
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
        self.port = 1935
        self._server = None
        self._running = False
        logger.info("RTMP服务器初始化完成")
    
    @property
    def streams(self) -> Dict[str, RTMPStream]:
        return _streams
    
    async def start(self, port: int = 1935):
        """启动RTMP服务器"""
        self.port = port
        self._running = True
        
        try:
            loop = asyncio.get_event_loop()
            self._server = await loop.create_server(
                lambda: asyncio.StreamReaderProtocol(
                    asyncio.StreamReader(),
                    self._client_connected
                ),
                '0.0.0.0',
                port
            )
            logger.info(f"RTMP服务器启动: rtmp://0.0.0.0:{port}")
            
            async with self._server:
                await self._server.serve_forever()
        except Exception as e:
            logger.error(f"RTMP服务器错误: {e}")
    
    async def _client_connected(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """新连接回调"""
        addr = writer.get_extra_info('peername')
        logger.info(f"[RTMP] 新连接: {addr}")
        
        controller = CameraRTMPController()
        await controller.client_callback(reader, writer)
        
        logger.info(f"[RTMP] 连接结束: {addr}")
    
    def get_frame(self, stream_key: str) -> Optional[bytes]:
        stream = _streams.get(stream_key)
        return stream.last_frame if stream else None
    
    def generate_mjpeg(self, stream_key: str) -> Generator[bytes, None, None]:
        last_frame = None
        while True:
            stream = _streams.get(stream_key)
            if stream and stream.last_frame:
                if stream.last_frame != last_frame:
                    last_frame = stream.last_frame
                    yield (
                        b'--frame\r\n'
                        b'Content-Type: image/jpeg\r\n\r\n' +
                        stream.last_frame +
                        b'\r\n'
                    )
            time.sleep(0.05)
    
    def get_status(self, stream_key: str) -> Optional[dict]:
        stream = _streams.get(stream_key)
        if not stream:
            return None
        
        from datetime import datetime
        is_online = (time.time() - stream.last_update) < 30 if stream.last_update else False
        
        return {
            "stream_key": stream.stream_key,
            "app": stream.app,
            "frame_count": stream.frame_count,
            "packet_count": stream.packet_count,
            "is_online": is_online,
            "last_update": datetime.fromtimestamp(stream.last_update).isoformat() if stream.last_update else None,
        }
    
    def list_streams(self) -> list:
        return [self.get_status(key) for key in _streams.keys()]
    
    def remove_stream(self, stream_key: str) -> bool:
        if stream_key in _streams:
            _stop_ffmpeg(stream_key)
            del _streams[stream_key]
            return True
        return False
    
    def stop(self):
        self._running = False
        for key in list(_streams.keys()):
            _stop_ffmpeg(key)
        logger.info("RTMP服务器已停止")


# 全局实例
rtmp_server = RTMPServer()
