"""ffmpeg检测和自动下载"""
import os
import platform
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
DEFAULT_BIN_DIR = PROJECT_ROOT / "bin"

# ffmpeg下载地址
FFMPEG_URLS = {
    "Windows": "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
    "Linux": "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz",
}

_ffmpeg_path = None


def get_ffmpeg_path() -> str:
    """
    获取ffmpeg路径
    优先级: 环境变量 > 项目bin目录 > 系统PATH
    """
    # 1. 环境变量
    env_path = os.getenv("FFMPEG_PATH")
    if env_path and Path(env_path).exists():
        return env_path
    
    # 2. 项目bin目录
    system = platform.system()
    if system == "Windows":
        bin_path = DEFAULT_BIN_DIR / "windows" / "ffmpeg.exe"
    else:
        bin_path = DEFAULT_BIN_DIR / "linux" / "ffmpeg"
    
    if bin_path.exists():
        return str(bin_path)
    
    # 3. 系统PATH
    ffmpeg_cmd = "ffmpeg.exe" if system == "Windows" else "ffmpeg"
    if shutil.which(ffmpeg_cmd):
        return ffmpeg_cmd
    
    return None


def download_ffmpeg() -> str:
    """下载ffmpeg到项目bin目录"""
    import zipfile
    import tarfile
    import lzma
    from urllib.request import urlretrieve
    
    system = platform.system()
    if system not in FFMPEG_URLS:
        raise RuntimeError(f"不支持的操作系统: {system}")
    
    url = FFMPEG_URLS[system]
    
    if system == "Windows":
        target_dir = DEFAULT_BIN_DIR / "windows"
        target_file = target_dir / "ffmpeg.exe"
    else:
        target_dir = DEFAULT_BIN_DIR / "linux"
        target_file = target_dir / "ffmpeg"
    
    target_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"开始下载ffmpeg...")
    print(f"下载地址: {url}")
    
    def progress(block_num, block_size, total_size):
        downloaded = block_num * block_size
        percent = min(100, downloaded * 100 // total_size)
        print(f"\r下载进度: {percent}%", end="", flush=True)
    
    temp_file = DEFAULT_BIN_DIR / f"ffmpeg_temp"
    try:
        urlretrieve(url, temp_file, progress)
        print()
        
        logger.info("解压中...")
        
        if system == "Windows":
            with zipfile.ZipFile(temp_file, 'r') as zf:
                for name in zf.namelist():
                    if name.endswith("bin/ffmpeg.exe"):
                        with zf.open(name) as src:
                            with open(target_file, 'wb') as dst:
                                dst.write(src.read())
                        break
        else:
            with lzma.open(temp_file) as xz:
                with tarfile.open(fileobj=xz) as tar:
                    for member in tar.getmembers():
                        if member.name.endswith("/ffmpeg") and member.isfile():
                            member.name = "ffmpeg"
                            tar.extract(member, target_dir)
                            break
            os.chmod(target_file, 0o755)
        
        logger.info(f"ffmpeg已安装: {target_file}")
        return str(target_file)
    finally:
        if temp_file.exists():
            temp_file.unlink()


def get_ffmpeg_cmd() -> str:
    """获取ffmpeg命令（带缓存和自动下载）"""
    global _ffmpeg_path
    
    if _ffmpeg_path:
        return _ffmpeg_path
    
    _ffmpeg_path = get_ffmpeg_path()
    
    if not _ffmpeg_path:
        logger.info("未找到ffmpeg，开始自动下载...")
        _ffmpeg_path = download_ffmpeg()
    
    return _ffmpeg_path
