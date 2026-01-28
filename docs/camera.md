# 摄像头视频流接收

支持两种方式：
- **HTTP推送** - 摄像头POST图片
- **RTMP推流** - 摄像头推送视频流

---

# 方式一：HTTP推送

## 架构说明

摄像头通过HTTP POST推送图片，前端通过MJPEG流查看：

```
摄像头 --HTTP POST--> nginx ---> Python:5000 ---> 内存缓存 --MJPEG--> 浏览器
```

## 摄像头配置

在摄像头的HTTP(S)推送设置中配置：
- **服务器地址**: `http://你的域名/camera/push/camera1`
- 其中 `camera1` 是摄像头ID（可自定义）

## nginx配置

标准HTTP反向代理即可：

```nginx
location /camera/ {
    proxy_pass http://127.0.0.1:5000/camera/;
    proxy_buffering off;  # 重要：MJPEG流需要关闭缓冲
    proxy_http_version 1.1;
    proxy_set_header Connection "";
}
```

## 启动服务

```bash
python main.py
```

## API接口

### 接收推流
```
POST /camera/push/{stream_id}
- 摄像头POST JPEG图片到此地址
- Content-Type: image/jpeg
```

### 查看视频流
```
GET /camera/view/{stream_id}
- 返回MJPEG流，可直接在<img>标签中使用
```

### 获取快照
```
GET /camera/snapshot/{stream_id}
- 返回单张JPEG图片
```

### 管理接口
```
GET /camera/list              # 列出所有摄像头
GET /camera/status/{stream_id}  # 查看摄像头状态
DELETE /camera/remove/{stream_id}  # 移除摄像头
```

## 前端播放示例

```html
<img src="http://你的域名/camera/view/camera1" alt="摄像头画面">
```

## 故障排查

1. **无画面**: 检查摄像头是否正在推送，访问 `/camera/list` 查看
2. **延迟高**: 检查nginx是否关闭了proxy_buffering
3. **图片不显示**: 确认摄像头推送的是JPEG格式

---

# 方式二：RTMP推流

## 架构说明

```
摄像头 --RTMP推流--> Python:1935(RTMP服务器) --ffmpeg转码--> MJPEG ---> 浏览器
```

## 摄像头配置

在摄像头的RTMP设置中配置：
- **服务器地址**: `rtmp://你的服务器IP:1935/live/camera1`
- 其中 `camera1` 是流名称（可自定义）

**注意**: RTMP需要直连服务器IP:1935端口，不走nginx代理

## 启动服务

```bash
python main.py
```

服务会同时启动：
- FastAPI: http://0.0.0.0:5000
- RTMP服务器: rtmp://0.0.0.0:1935

## API接口

```
GET /rtmp/list                 # 列出所有流
GET /rtmp/view/{stream_key}    # 查看MJPEG视频流
GET /rtmp/snapshot/{stream_key} # 获取快照
GET /rtmp/status/{stream_key}  # 查看流状态
DELETE /rtmp/remove/{stream_key} # 移除流
```

## 前端播放

```html
<img src="http://你的域名/rtmp/view/camera1" alt="摄像头画面">
```

## ffmpeg自动管理

首次运行时如果没有ffmpeg，会自动下载到 `bin/` 目录。

也可以手动指定 ffmpeg 路径：
```env
FFMPEG_PATH=C:/path/to/ffmpeg.exe
```

## 故障排查

1. **端口1935被占用**: 检查是否有其他RTMP服务
2. **无画面**: 检查摄像头是否正在推流，访问 `/rtmp/list` 查看
3. **ffmpeg错误**: 检查bin/目录下是否有ffmpeg
