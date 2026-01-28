# 实验接口说明

本文档描述 `app/routers/experiment.py` 中与实验相关的对外接口（均以 `/target` 为前缀）。

## 启动实验（真实）

- 路径：`POST /target/start-experiment`
- 作用：
  - 先从内网接口拉取实验列表
  - 按 `exp_code` 匹配对应的实验 item（字段 `experienceCode`）
  - 将该 item 作为 payload 调用内网的“启动实验”接口

请求体：
```json
{
  "authorization": "Bearer ...",
  "exp_code": "EXP_XXX"
}
```

## 启动实验（Mock）

- 路径：`POST /target/mock/start-expirement`
- 作用：
  - 与真实启动流程一致：会拉取实验列表并按 `exp_code` 匹配
  - 但最后一步“发送启动实验请求”被注释掉
  - 直接返回匹配到的实验 item（JSON 对象）

请求体：
```json
{
  "authorization": "Bearer ...",
  "exp_code": "EXP_XXX"
}
```

返回：
- `200`：返回匹配到的实验 item
- `404`：未找到对应 `exp_code`
- `502`：无法连接到内网服务（SSH 隧道/内网接口不可用）
