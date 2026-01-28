"""SSH隧道管理"""
import threading
import time
import logging
from sshtunnel import SSHTunnelForwarder
from .config import SSH_CONFIG

logger = logging.getLogger(__name__)

_tunnel_instance = None
_tunnel_lock = threading.Lock()
_heartbeat_thread = None
_heartbeat_running = False


def create_tunnel():
    """创建新的SSH隧道"""
    global _tunnel_instance
    _tunnel_instance = SSHTunnelForwarder(
        (SSH_CONFIG["host"], SSH_CONFIG["port"]),
        ssh_username=SSH_CONFIG["username"],
        ssh_password=SSH_CONFIG["password"],
        remote_bind_address=(SSH_CONFIG["remote_host"], SSH_CONFIG["remote_port"]),
        local_bind_address=("127.0.0.1", SSH_CONFIG["local_port"]),
        set_keepalive=30,
        allow_agent=False,
        ssh_pkey=None,
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


def _heartbeat_monitor():
    """心跳监控线程"""
    global _tunnel_instance, _heartbeat_running
    while _heartbeat_running:
        try:
            with _tunnel_lock:
                if _tunnel_instance and not _tunnel_instance.is_active:
                    logger.warning("检测到SSH隧道断开，尝试重连...")
                    try:
                        _tunnel_instance.stop()
                    except Exception:
                        pass
                    create_tunnel()
                    logger.info("SSH隧道重连成功")
        except Exception as e:
            logger.error(f"心跳检测异常: {e}")
        time.sleep(15)


def start_heartbeat():
    """启动心跳监控"""
    global _heartbeat_thread, _heartbeat_running
    _heartbeat_running = True
    _heartbeat_thread = threading.Thread(target=_heartbeat_monitor, daemon=True)
    _heartbeat_thread.start()
    logger.info("心跳监控已启动")


def stop_heartbeat():
    """停止心跳监控"""
    global _heartbeat_running
    _heartbeat_running = False
    logger.info("心跳监控已停止")


def stop_tunnel():
    """停止SSH隧道"""
    global _tunnel_instance
    if _tunnel_instance:
        _tunnel_instance.stop()
        logger.info("SSH隧道已关闭")
