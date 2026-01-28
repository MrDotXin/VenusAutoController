"""请求/响应数据模型"""
from pydantic import BaseModel


# ============== 实验相关 ==============
class LoginRequest(BaseModel):
    accountName: str
    accountPwd: str


class AuthRequest(BaseModel):
    authorization: str


class ExperimentListRequest(BaseModel):
    authorization: str
    pageNum: int = 1
    pageSize: int = 10


class CreateExperimentRequest(BaseModel):
    authorization: str
    name: str


class StartExperimentRequest(BaseModel):
    authorization: str
    exp_code: str


class DeleteExperimentRequest(BaseModel):
    authorization: str
    id: int


# ============== 摄像头相关 ==============
class CameraRequest(BaseModel):
    camera_id: str
    stream_url: str


class CameraIdRequest(BaseModel):
    camera_id: str


class FramePushRequest(BaseModel):
    stream_id: str
    frame_base64: str
