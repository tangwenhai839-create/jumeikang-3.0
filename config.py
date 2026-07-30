# 体重管理系统配置文件

import os
import platform

# 服务器配置
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 5000
DEBUG = False

# 数据库
BASEDIR = os.path.abspath(os.path.dirname(__file__))
DB_DIR = os.path.join(BASEDIR, 'db')
DB_PATH = os.path.join(DB_DIR, 'weight.db')
os.makedirs(DB_DIR, exist_ok=True)

# ArcFace SDK 配置
SYSTEM = platform.system()
SDK_DIR = os.path.join(BASEDIR, 'sdk')
FACE_RECOGNITION_THRESHOLD = 0.8
MAX_FACE_COUNT = 5
DETECT_MODE = 0
FACE_SCALE = 40

# 称重相关
MAX_WEIGHT = 300.0
MIN_WEIGHT = 20.0
WEIGHT_DECIMALS = 1
WEEK_START_DAY = 0

# Demo 模式 (有 SDK 时改为 False)
# DEMO_MODE = False 使用真实 ArcFace 引擎 (激活超时由 engine 内部处理)
DEMO_MODE = False

# 人脸活体验证总开关 (后端每次从数据库 settings 读取，可被设置页覆盖)
LIVENESS_ENABLED = True

# 串口秤配置
SCALE_PORT = 'COM3'
SCALE_BAUDRATE = 9600
SCALE_TIMEOUT = 2.0


def get_sdk_path():
    """返回当前平台的 ArcFace SDK 路径"""
    if SYSTEM == 'Windows':
        return os.path.join(SDK_DIR, 'win64', 'libarcsoft_face_engine.dll')
    else:
        return os.path.join(SDK_DIR, 'linux', 'libarcsoft_face_engine.so')
