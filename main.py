"""SSH隧道代理服务 - 启动入口"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=5000, reload=True)
