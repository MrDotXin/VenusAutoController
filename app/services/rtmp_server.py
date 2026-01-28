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
    """流信息"""
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
    使用原生TCP接收RTMP推流
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
        self._server = None
        self._running = False
        logger.info("RTMP服务器初始化完成")
    
    async def start(self, port: int = 1935):
        """启动RTMP服务器"""
        self.port = port
        self._running = True
        
        try:
            self._server = await asyncio.start_server(
                self._handle_client,
                '0.0.0.0',
                port
            )
            logger.info(f"RTMP服务器启动: rtmp://0.0.0.0:{port}")
            
            async with self._server:
                await self._server.serve_forever()
        except Exception as e:
            logger.error(f"RTMP服务器错误: {e}")
    
    async def _read_exact(self, reader: asyncio.StreamReader, n: int, timeout: float = 10) -> Optional[bytes]:
        """循环读取指定字节数"""
        data = b''
        try:
            while len(data) < n:
                chunk = await asyncio.wait_for(
                    reader.read(n - len(data)),
                    timeout=timeout
                )
                if not chunk:
                    return None
                data += chunk
            return data
        except asyncio.TimeoutError:
            return None
    
    async def _handle_client
        """处理客户端连接"""
        addr = writer.get_extra_info('peername')
        logger.info(f"[RTMP] 新连接: {addr}")
        
        stream_key = None
        try:
            # RTMP握手 - 循环读取确保收到完整数据
            # 读取C0+C1 (1 + 1536 = 1537 bytes)
            c0c1 = await self._read_exact(reader, 1537, timeout=10)
            if not c0c1:
                logger.warning(f"[RTMP] 握手失败: 读取C0+C1超时")
                return
            
            logger.info(f"[RTMP] 收到C0+C1: {len(c0c1)} bytes")
            
            # 发送S0+S1+S2
            s0 = bytes([3])  # RTMP版本
            s1 = b'\x00' * 4 + b'\x00' * 4 + c0c1[1:][:1528]  # 时间戳 + 零 + 随机数据
            s2 = c0c1[1:]  # 回显c1
            writer.write(s0 + s1 + s2)
            await writer.drain()
            logger.info(f"[RTMP] 发送S0+S1+S2")
            
            # 读取C2 (1536 bytes)
            c2 = await self._read_exact(reader, 1536, timeout=10)
            if not c2:
                logger.warning(f"[RTMP] 握手失败: 读取C2超时")
                return
            logger.info(f"[RTMP] 收到C2: {len(c2)} bytes")
            
            # 握手完成
            logger.info(f"[RTMP] 握手完成: {addr}")
            
            # 为这个连接创建流
            stream_key = f"stream_{int(time.time())}"
            self.streams[stream_key] = RTMPStream(
                stream_key=stream_key,
                last_update=time.time()
            )
            stream = self.streams[stream_key]
            
            # 启动ffmpeg
            self._start_ffmpeg(stream_key)
            
            # 读取RTMP数据并写入ffmpeg
            while self._running and stream._running:
                try:
                    data = await asyncio.wait_for(reader.read(4096), timeout=30)
                    if not data:
                        logger.info(f"[RTMP] 连接关闭: {addr}")
                        break
                    
                    stream.frame_count += 1
                    stream.last_update = time.time()
                    
                    # 写入ffmpeg
                    if stream.ffmpeg_process and stream.ffmpeg_process.stdin:
                        try:
                            stream.ffmpeg_process.stdin.write(data)
                            stream.ffmpeg_process.stdin.flush()
                        except:
                            pass
                    
                    # 每1000个包输出一次统计
                    if stream.frame_count % 1000 == 0:
                        logger.info(f"[{stream_key}] 已接收 {stream.frame_count} 个数据包")
                        
                except asyncio.TimeoutError:
                    logger.warning(f"[RTMP] 超时无数据: {addr}")
                    break
                    
        except asyncio.TimeoutError:
            logger.warning(f"[RTMP] 握手超时: {addr}")
        except Exception as e:
            logger.error(f"[RTMP] 处理错误: {addr} - {e}")
        finally:
            writer.close()
            if stream_key:
                self._stop_ffmpeg(stream_key)
                if stream_key in self.streams:
                    del self.streams[stream_key]
            logger.info(f"[RTMP] 连接结束: {addr}")
    
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
                stderr=subprocess.PIPE
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
        frame_count = 0
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
                    frame_count += 1
                    
                    if frame_count % 100 == 0:
                        logger.info(f"[{stream_key}] 已转码 {frame_count} 帧")
                    
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
