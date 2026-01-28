# 摄像头HTTP推流接收

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
