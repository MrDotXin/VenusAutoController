"""
RTMP服务器模块
接收摄像头RTMP推流，转码为MJPEG供前端查看
"""
import asyncio
import logging
import subprocess
import threading
import time
from typing import Dict, Optional, Generator
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RTMPStream:
    """RTMP流信息"""
    stream_key: str
    app: str = "live"
    frame_count: int = 0
    last_update: float = 0
    last_frame: Optional[bytes] = None
    ffmpeg_process: Optional[subprocess.Popen] = None
    _running: bool = False


class RTMPServer:
    """
    RTMP服务器
    使用pyrtmp接收推流，ffmpeg转码
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
        self.streams: Dict[str, RTMPStream] = {}
        self.port = 1935
        self._server_task = None
        self._running = False
        logger.info("RTMP服务器初始化完成")
    
    async def start(self, port: int = 1935):
        """启动RTMP服务器"""
        from pyrtmp import StreamClosedException
        from pyrtmp.flv import FLVFileWriter, FLVMediaType
        from pyrtmp.session_manager import SessionManager
        from pyrtmp.rtmp import SimpleRTMPController, RTMPProtocol
        
        self.port = port
        self._running = True
        
        controller = SimpleRTMPController()
        
        @controller.on_connect
        async def on_connect(session_id, message):
            logger.info(f"[RTMP] 连接: session={session_id}")
            return True
        
        @controller.on_publish
        async def on_publish(session_id, message):
            stream_key = message.publishing_name
            app = message.publishing_type
            logger.info(f"[RTMP] 推流开始: {app}/{stream_key}")
            
            # 创建流
            self.streams[stream_key] = RTMPStream(
                stream_key=stream_key,
                app=app,
                last_update=time.time()
            )
            
            # 启动ffmpeg转码
            self._start_ffmpeg(stream_key)
            return True
        
        @controller.on_video
        async def on_video(session_id, message):
            stream_key = self._get_stream_key(session_id)
            if stream_key and stream_key in self.streams:
                stream = self.streams[stream_key]
                stream.frame_count += 1
                stream.last_update = time.time()
                
                # 写入ffmpeg stdin
                if stream.ffmpeg_process and stream.ffmpeg_process.stdin:
                    try:
                        stream.ffmpeg_process.stdin.write(message.payload)
                    except:
                        pass
        
        @controller.on_stream_closed
        async def on_stream_closed(session_id, message):
            stream_key = self._get_stream_key(session_id)
            logger.info(f"[RTMP] 流关闭: {stream_key}")
            if stream_key:
                self._stop_ffmpeg(stream_key)
        
        session_manager = SessionManager(controller=controller)
        
        try:
            server = await asyncio.start_server(
                lambda r, w: RTMPProtocol(controller=controller, session_manager=session_manager).connection_made(r, w),
                '0.0.0.0', 
                port
            )
            logger.info(f"RTMP服务器启动: rtmp://0.0.0.0:{port}")
            
            async with server:
                await server.serve_forever()
        except Exception as e:
            logger.error(f"RTMP服务器错误: {e}")
    
    def _get_stream_key(self, session_id) -> Optional[str]:
        """根据session_id获取stream_key"""
        # 简化处理，返回第一个活跃的流
        for key, stream in self.streams.items():
            if stream._running:
                return key
        return None
    
    def _start_ffmpeg(self, stream_key: str):
        """启动ffmpeg转码进程"""
        from ..core.ffmpeg import get_ffmpeg_cmd
        
        stream = self.streams.get(stream_key)
        if not stream:
            return
        
        ffmpeg_cmd = get_ffmpeg_cmd()
        if not ffmpeg_cmd:
            logger.error("ffmpeg不可用")
            return
        
        # ffmpeg命令：从stdin读取FLV，输出MJPEG帧
        cmd = [
            ffmpeg_cmd,
            '-f', 'flv',
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
                stderr=subprocess.DEVNULL
            )
            stream._running = True
            
            # 启动读取线程
            threading.Thread(
                target=self._read_ffmpeg_output,
                args=(stream_key,),
                daemon=True
            ).start()
            
            logger.info(f"[{stream_key}] ffmpeg转码已启动")
        except Exception as e:
            logger.error(f"[{stream_key}] ffmpeg启动失败: {e}")
    
    def _read_ffmpeg_output(self, stream_key: str):
        """读取ffmpeg输出的MJPEG帧"""
        stream = self.streams.get(stream_key)
        if not stream or not stream.ffmpeg_process:
            return
        
        buffer = b''
        while stream._running:
            try:
                chunk = stream.ffmpeg_process.stdout.read(4096)
                if not chunk:
                    break
                
                buffer += chunk
                
                # 查找JPEG帧 (FFD8...FFD9)
                while True:
                    start = buffer.find(b'\xff\xd8')
                    if start == -1:
                        break
                    
                    end = buffer.find(b'\xff\xd9', start + 2)
                    if end == -1:
                        break
                    
                    # 提取完整帧
                    frame = buffer[start:end + 2]
                    stream.last_frame = frame
                    buffer = buffer[end + 2:]
                    
            except Exception as e:
                logger.error(f"[{stream_key}] 读取ffmpeg输出错误: {e}")
                break
    
    def _stop_ffmpeg(self, stream_key: str):
        """停止ffmpeg进程"""
        stream = self.streams.get(stream_key)
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
    
    def get_frame(self, stream_key: str) -> Optional[bytes]:
        """获取最新帧"""
        stream = self.streams.get(stream_key)
        if stream:
            return stream.last_frame
        return None
    
    def generate_mjpeg(self, stream_key: str) -> Generator[bytes, None, None]:
        """生成MJPEG视频流"""
        last_frame = None
        while True:
            stream = self.streams.get(stream_key)
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
        """获取流状态"""
        stream = self.streams.get(stream_key)
        if not stream:
            return None
        
        from datetime import datetime
        is_online = (time.time() - stream.last_update) < 30 if stream.last_update else False
        
        return {
            "stream_key": stream.stream_key,
            "app": stream.app,
            "frame_count": stream.frame_count,
            "is_online": is_online,
            "last_update": datetime.fromtimestamp(stream.last_update).isoformat() if stream.last_update else None,
        }
    
    def list_streams(self) -> list:
        """列出所有流"""
        return [self.get_status(key) for key in self.streams.keys()]
    
    def remove_stream(self, stream_key: str) -> bool:
        """移除流"""
        if stream_key in self.streams:
            self._stop_ffmpeg(stream_key)
            del self.streams[stream_key]
            return True
        return False
    
    def stop(self):
        """停止服务器"""
        self._running = False
        for key in list(self.streams.keys()):
            self._stop_ffmpeg(key)
        logger.info("RTMP服务器已停止")


# 全局实例
rtmp_server = RTMPServer()
