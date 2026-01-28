# RTMP 视频流接口文档

## 架构说明

```
摄像头 --RTMP推流--> SRS Docker (:1935)
                         |
                         ├── HTTP-FLV/HLS (:5002) --> Nginx --> 前端播放
                         |
                         └── Python后端 (ffmpeg截图) --> 快照API
```

## 推流地址

摄像头/OBS 推流到：
```
rtmp://服务器IP:1935/live/{stream_key}
```

示例：
```
rtmp://venusfactory.cn:1935/live/camera1
```

## 前端播放地址

### HTTP-FLV（推荐，低延迟）
```
https://venusfactory.cn/venus-auto-camera/live/{stream_key}.flv
```

前端使用 flv.js 播放：
```html
<video id="video" controls></video>
<script src="https://cdn.jsdelivr.net/npm/flv.js/dist/flv.min.js"></script>
<script>
  if (flvjs.isSupported()) {
    const player = flvjs.createPlayer({
      type: 'flv',
      url: 'https://venusfactory.cn/venus-auto-camera/live/camera1.flv'
    });
    player.attachMediaElement(document.getElementById('video'));
    player.load();
    player.play();
  }
</script>
```

### HLS（兼容性好，延迟较高）
```
https://venusfactory.cn/venus-auto-camera/live/{stream_key}.m3u8
```

前端使用 hls.js 播放：
```html
<video id="video" controls></video>
<script src="https://cdn.jsdelivr.net/npm/hls.js/dist/hls.min.js"></script>
<script>
  const video = document.getElementById('video');
  if (Hls.isSupported()) {
    const hls = new Hls();
    hls.loadSource('https://venusfactory.cn/venus-auto-camera/live/camera1.m3u8');
    hls.attachMedia(video);
  }
</script>
```

---

## 后端 API 接口

基础路径：`https://venusfactory.cn/venus-auto/rtmp`

### 1. 获取快照

获取指定流的最新截图（JPEG 格式）

**请求**
```
GET /rtmp/snapshot/{stream_key}
```

**参数**
| 参数 | 类型 | 说明 |
|------|------|------|
| stream_key | string | 流名称，如 `camera1` |

**响应**
- 成功：返回 JPEG 图片 (`Content-Type: image/jpeg`)
- 失败：404

**示例**
```
GET https://venusfactory.cn/venus-auto/rtmp/snapshot/camera1
```

**说明**
- 首次请求会自动注册该流并开始每秒截图
- 截图来源于 SRS 的 RTMP 流

---

### 2. 获取流状态

查询指定流的状态信息

**请求**
```
GET /rtmp/status/{stream_key}
```

**响应**
```json
{
  "success": true,
  "data": {
    "stream_key": "camera1",
    "capture_count": 120,
    "is_online": true,
    "last_update": "2026-01-28T15:50:00"
  }
}
```

**字段说明**
| 字段 | 类型 | 说明 |
|------|------|------|
| stream_key | string | 流名称 |
| capture_count | int | 已截图次数 |
| is_online | bool | 是否在线（10秒内有更新） |
| last_update | string | 最后更新时间 |

---

### 3. 列出所有流

获取所有已注册的流列表

**请求**
```
GET /rtmp/list
```

**响应**
```json
{
  "success": true,
  "data": [
    {
      "stream_key": "camera1",
      "capture_count": 120,
      "is_online": true,
      "last_update": "2026-01-28T15:50:00"
    }
  ]
}
```

---

### 4. 移除流

停止对指定流的截图

**请求**
```
DELETE /rtmp/remove/{stream_key}
```

**响应**
```json
{
  "success": true,
  "message": "流 camera1 已移除"
}
```

---

## 完整示例

### 场景：显示摄像头实时画面 + 点击截图

```html
<!DOCTYPE html>
<html>
<head>
  <title>摄像头监控</title>
  <script src="https://cdn.jsdelivr.net/npm/flv.js/dist/flv.min.js"></script>
</head>
<body>
  <h2>实时视频</h2>
  <video id="video" width="640" height="480" controls></video>
  
  <h2>快照</h2>
  <button onclick="takeSnapshot()">截图</button>
  <img id="snapshot" width="320" height="240">
  
  <script>
    // 播放视频流
    if (flvjs.isSupported()) {
      const player = flvjs.createPlayer({
        type: 'flv',
        url: 'https://venusfactory.cn/venus-auto-camera/live/camera1.flv'
      });
      player.attachMediaElement(document.getElementById('video'));
      player.load();
      player.play();
    }
    
    // 获取快照
    function takeSnapshot() {
      document.getElementById('snapshot').src = 
        'https://venusfactory.cn/venus-auto/rtmp/snapshot/camera1?t=' + Date.now();
    }
  </script>
</body>
</html>
```
