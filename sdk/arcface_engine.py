# ArcFace 人脸引擎 Python 封装 (V3.0 SDK)
# 支持 Windows DLL / Linux SO 双平台
# 无 SDK 时自动降级为 demo 模式

import os
import sys
import ctypes
import base64
import hashlib
import logging

try:
    import numpy as np
except ImportError:
    np = None

from config import SDK_DIR, FACE_RECOGNITION_THRESHOLD, DEMO_MODE, get_sdk_path

# ─── 日志 ──────────────────────────────────────────
logger = logging.getLogger('FaceEngine')

class FaceNotInitializedError(Exception):
    pass


# ─── ArcFace SDK 常量 ────────────────────────────
ASF_FACE_DETECT       = 0x00000001
ASF_FACERECOGNITION   = 0x00000004
ASF_LIVENESS          = 0x00000080
ASF_IR_LIVENESS       = 0x00000400
ASF_DETECT_MODE_IMAGE = 0xFFFFFFFF
ASF_OP_0_ONLY         = 0x1
ASF_OP_90_ONLY        = 0x2
ASF_OP_180_ONLY       = 0x3
ASF_OP_270_ONLY       = 0x4
ASF_DETECT_MODEL_RGB  = 0x1
ASF_LIFE_PHOTO        = 0x1
ASF_REC_LARGE       = 0x1
ASF_REC_MIDDLE      = 0x2
ASVL_PAF_RGB24_B8G8R8 = 0x201  # BGR 24bit


# ─── C 结构体定义 ────────────────────────────────

class MRECT(ctypes.Structure):
    """人脸矩形框"""
    _fields_ = [
        ("left",   ctypes.c_int),
        ("top",    ctypes.c_int),
        ("right",  ctypes.c_int),
        ("bottom", ctypes.c_int),
    ]


class ASF_FaceDataInfo(ctypes.Structure):
    """单张人脸信息（V5.0 新增）"""
    _fields_ = [
        ("data",     ctypes.c_void_p),   # MPVoid
        ("dataSize", ctypes.c_int),      # MInt32
    ]


class ASF_Face3DAngleInfo(ctypes.Structure):
    """人脸3D角度信息（V5.0 新增）"""
    _fields_ = [
        ("pitch", ctypes.c_float),
        ("yaw",   ctypes.c_float),
        ("roll",  ctypes.c_float),
        ("status", ctypes.c_int),
    ]


class ASF_SingleFaceInfo(ctypes.Structure):
    """V5.0 版本 — 增加了 faceDataInfo"""
    _fields_ = [
        ("faceRect",     MRECT),              # 人脸框
        ("faceOrient",   ctypes.c_int),     # 角度
        ("faceDataInfo", ASF_FaceDataInfo),  # V5.0 新增
    ]


class ASF_MultiFaceInfo(ctypes.Structure):
    """V5.0 版本 — 字段顺序和数量均有变化"""
    _fields_ = [
        ("faceNum",              ctypes.c_int),                   # 人脸个数
        ("faceRect",             ctypes.POINTER(MRECT)),         # 人脸框指针
        ("faceOrient",           ctypes.POINTER(ctypes.c_int)),   # 角度指针
        ("faceID",               ctypes.POINTER(ctypes.c_int)),   # face ID 指针
        ("faceDataInfoList",     ctypes.POINTER(ASF_FaceDataInfo)),# V5.0 新增
        ("faceIsWithinBoundary", ctypes.POINTER(ctypes.c_int)),   # V5.0 新增
        ("foreheadRect",         ctypes.POINTER(MRECT)),          # V5.0 新增
        ("face3DAngleInfo",      ASF_Face3DAngleInfo),            # V5.0 新增
    ]


class ASF_FaceFeature(ctypes.Structure):
    _fields_ = [
        ("feature",     ctypes.POINTER(ctypes.c_byte)),
        ("featureSize", ctypes.c_int),
    ]


class ASF_LivenessInfo(ctypes.Structure):
    # Doc 4.11: isLive=1 real, 0 spoof/photo, -1 unknown, -2 face>1, -3 too small, -4 angle, -5 boundary, -6 depth, -7 ir bright, -8 ir dark, -100 quality
    _fields_ = [
        ("isLive", ctypes.POINTER(ctypes.c_int)),
        ("num",    ctypes.c_int),
    ]
class ASF_LivenessThreshold(ctypes.Structure):
    _fields_ = [
        ("thresholdmodel_BGR", ctypes.c_float),
        ("thresholdmodel_IR",  ctypes.c_float),
    ]


class ASF_ImageData(ctypes.Structure):
    _fields_ = [
        ("u32PixelArrayFormat", ctypes.c_uint32),
        ("i32Width", ctypes.c_int32),
        ("i32Height", ctypes.c_int32),
        ("ppu8Plane", ctypes.POINTER(ctypes.c_ubyte) * 4),
        ("pi32Pitch", ctypes.c_int32 * 4),
    ]

def _zero_struct(cls):
    """创建并清零 ctypes 结构体实例（避免 5.0 SDK 因野指针字段出错）"""
    inst = cls()
    ctypes.memset(ctypes.byref(inst), 0, ctypes.sizeof(inst))
    return inst


class FaceEngine:
    """ArcFace SDK V3.0 人脸引擎"""

    def __init__(self):
        self._lib = None
        self._engine = None
        self._initialized = False
        self._demo_mode = DEMO_MODE
        self._liveness_available = False  # 活体检测是否真正可用
        # 人脸特征内存缓存（避免每次识别都查数据库）
        self._feature_cache = None
        self._cache_timestamp = 0
        self._cache_ttl = 300  # 缓存有效期 5 分钟

    # ─── 激活 / 初始化 ─────────────────────────

    def _activate_with_timeout(self, app_id, sdk_key, timeout=10):
        """激活SDK带超时保护，网络不通时10秒自动降级"""
        import threading
        result = [None]
        done = [False]

        def _do():
            try:
                ret = self._lib.ASFActivation(
                    app_id.encode('utf-8'),
                    sdk_key.encode('utf-8')
                )
                result[0] = ret
            except Exception:
                result[0] = -1
            finally:
                done[0] = True

        t = threading.Thread(target=_do, daemon=True)
        t.start()
        t.join(timeout)

        if not done[0]:
            print(f'[FaceEngine] Activation timed out ({timeout}s), demo mode')
            return -2
        return result[0]

    def initialize(self, app_id='', sdk_key=''):
        if self._demo_mode:
            print('[FaceEngine] Demo mode')
            self._initialized = True
            return True

        sdk_path = get_sdk_path()
        if not os.path.exists(sdk_path):
            print(f'[FaceEngine] SDK not found at {sdk_path}, demo mode')
            self._demo_mode = True
            self._initialized = True
            return True

        try:
            self._lib = ctypes.cdll.LoadLibrary(sdk_path)

            # 激活
            if app_id and sdk_key:
                ret = self._activate_with_timeout(app_id, sdk_key)
                print(f'[FaceEngine] Activation: {ret}')
                if ret != 0 and ret != 90114:  # 90114 = already activated
                    print(f'[FaceEngine] Activation failed (code={ret}), continuing anyway')

            # ── 初始化引擎 ──
            self._lib.ASFInitEngine.restype = ctypes.c_int
            self._lib.ASFInitEngine.argtypes = [
                ctypes.c_int, ctypes.c_int, ctypes.c_int,
                ctypes.c_int, ctypes.c_int,
                ctypes.POINTER(ctypes.c_void_p),
            ]

            engine_handle = ctypes.c_void_p()
            combined_mask = ASF_FACE_DETECT | ASF_FACERECOGNITION | ASF_LIVENESS
            ret = self._lib.ASFInitEngine(
                ASF_DETECT_MODE_IMAGE,
                ASF_OP_0_ONLY,
                5,              # maxNum
                combined_mask,  # combinedMask
                ASF_REC_LARGE,  # recModel
                ctypes.byref(engine_handle),
            )

            if ret != 0:
                print(f'[FaceEngine] Init failed (code={ret}), demo mode')
                self._demo_mode = True
                self._initialized = True
                return True

            self._engine = engine_handle

            # ── 统一设置所有 API 函数签名 ──
            self._setup_api_signatures()

            # ── 设置活体检测参数 ──
            self._setup_liveness_param()

            # ── 活体检测自检 ──
            self._liveness_available = self._self_test_liveness()
            if self._liveness_available:
                print('[FaceEngine] OK (liveness: OK)')
            else:
                print('[FaceEngine] OK (liveness: DISABLED)')

            self._initialized = True
            return True

        except Exception as e:
            print(f'[FaceEngine] Error: {e}, demo mode')
            import traceback
            traceback.print_exc()
            self._demo_mode = True
            self._initialized = True
            return True

    def _setup_api_signatures(self):
        """统一声明所有 SDK 函数的参数/返回值类型"""
        lib = self._lib

        # ASFDetectFaces (old-style 6-param API)
        lib.ASFDetectFaces.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.POINTER(ASF_MultiFaceInfo),
            ctypes.c_int,
        ]
        lib.ASFDetectFaces.restype = ctypes.c_int

        # ASFFaceFeatureExtract (V5.0 API with 9 parameters)
        lib.ASFFaceFeatureExtract.argtypes = [
            ctypes.c_void_p,                     # hEngine
            ctypes.c_int,                        # width
            ctypes.c_int,                        # height
            ctypes.c_int,                        # format
            ctypes.POINTER(ctypes.c_ubyte),      # imgData
            ctypes.POINTER(ASF_SingleFaceInfo),  # singleFaceInfo
            ctypes.c_int,                        # registerOrNot (1=register, 0=recognize)
            ctypes.c_int,                        # mask (1=with mask, 0=without)
            ctypes.POINTER(ASF_FaceFeature),      # feature
        ]
        lib.ASFFaceFeatureExtract.restype = ctypes.c_int

        # ASFProcess (old-style API, for liveness/age/gender)
        lib.ASFProcess.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.POINTER(ASF_MultiFaceInfo),
            ctypes.c_int,
        ]
        lib.ASFProcess.restype = ctypes.c_int
        
        # ASFProcessEx (V5.0 API, for liveness/age/gender)
        lib.ASFProcessEx.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ASF_ImageData),
            ctypes.POINTER(ASF_MultiFaceInfo),
            ctypes.c_int,
        ]
        lib.ASFProcessEx.restype = ctypes.c_int

        # ASFGetLivenessScore
        lib.ASFGetLivenessScore.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ASF_LivenessInfo),
        ]
        lib.ASFGetLivenessScore.restype = ctypes.c_int

        # ASFSetLivenessParam
        try:
            lib.ASFSetLivenessParam.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ASF_LivenessThreshold),
            ]
            lib.ASFSetLivenessParam.restype = ctypes.c_int
        except Exception:
            pass  # 某些版本可能没有此函数

        # ASFFaceFeatureCompare
        lib.ASFFaceFeatureCompare.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ASF_FaceFeature),
            ctypes.POINTER(ASF_FaceFeature),
            ctypes.POINTER(ctypes.c_float),
            ctypes.c_int,
        ]
        lib.ASFFaceFeatureCompare.restype = ctypes.c_int

    def _setup_liveness_param(self):
        """设置活体检测阈值"""
        if not self._lib:
            return
        try:
            # RGB 活体检测推荐阈值: 0.5~0.8
            # 值越低越严格（要求更高的活体置信度）
            threshold = ASF_LivenessThreshold()
            threshold.thresholdmodel_BGR = 0.5
            threshold.thresholdmodel_IR = 0.5
            ret = self._lib.ASFSetLivenessParam(self._engine, ctypes.byref(threshold))
            if ret == 0:
                print(f'[FaceEngine] Liveness threshold set to 0.5')
            else:
                print(f'[FaceEngine] ASFSetLivenessParam failed (code={ret}), using defaults')
        except AttributeError:
            print('[FaceEngine] ASFSetLivenessParam not available, using defaults')
        except Exception as e:
            print(f'[FaceEngine] ASFSetLivenessParam error: {e}')

    def _self_test_liveness(self):
        """用一张纯色测试图片自检活体功能是否可用"""
        if not self._lib or not self._engine:
            return False
        try:
            # 创建一张 200x200 的纯灰测试图
            test_img = np.ones((200, 200, 3), dtype=np.uint8) * 128
            w, h = test_img.shape[1], test_img.shape[0]
            img_ptr = test_img.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))

            # 直接测试 ASFProcess 是否能被调用（即使没有检测到人脸也应该返回错误码，而不是崩溃）
            faces = _zero_struct(ASF_MultiFaceInfo)
            ret_detect = self._lib.ASFDetectFaces(
                self._engine, w, h, ASVL_PAF_RGB24_B8G8R8,
                img_ptr, ctypes.byref(faces), ASF_DETECT_MODEL_RGB)

            if ret_detect == 0 and faces.faceNum > 0:
                # 意外检测到了人脸，用实际图像测活体
                img_data = ASF_ImageData()
                img_data.u32PixelArrayFormat = ASVL_PAF_RGB24_B8G8R8
                img_data.i32Width = w
                img_data.i32Height = h
                img_data.ppu8Plane[0] = img_ptr
                img_data.pi32Pitch[0] = w * 3
                ret_process = self._lib.ASFProcessEx(
                    self._engine, ctypes.byref(img_data), ctypes.byref(faces), ASF_LIVENESS)
                print(f'[FaceEngine] Liveness self-test: ASFProcess returned {ret_process}')
                if ret_process == 0:
                    liveness_info = _zero_struct(ASF_LivenessInfo)
                    ret_score = self._lib.ASFGetLivenessScore(
                        self._engine, ctypes.byref(liveness_info))
                    print(f'[FaceEngine] Liveness self-test: ASFGetLivenessScore returned {ret_score}')
                    return ret_score == 0
                else:
                    return False
            else:
                # 纯灰图检测不到人脸 → 正常。用实际照片测试
                print(f'[FaceEngine] Liveness self-test: no face in test image (expected), testing with real image bypass...')

                # 创建一个简单的人脸模拟图（椭圆+斑块）
                import cv2
                test_img_real = np.zeros((200, 200, 3), dtype=np.uint8)
                cv2.ellipse(test_img_real, (100, 100), (60, 80), 0, 0, 360, (200, 180, 160), -1)
                cv2.ellipse(test_img_real, (80, 80), (12, 10), 0, 0, 360, (80, 100, 120), -1)
                cv2.ellipse(test_img_real, (120, 80), (12, 10), 0, 0, 360, (80, 100, 120), -1)
                cv2.ellipse(test_img_real, (100, 120), (15, 8), 0, 0, 360, (100, 80, 80), -1)

                w2, h2 = test_img_real.shape[1], test_img_real.shape[0]
                img_ptr2 = test_img_real.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))
                faces2 = _zero_struct(ASF_MultiFaceInfo)
                ret_detect2 = self._lib.ASFDetectFaces(
                    self._engine, w2, h2, ASVL_PAF_RGB24_B8G8R8,
                    img_ptr2, ctypes.byref(faces2), ASF_DETECT_MODEL_RGB)
                print(f'[FaceEngine] Liveness self-test: ASFDetectFaces returned {ret_detect2}, faces={faces2.faceNum}')

                if ret_detect2 != 0 or faces2.faceNum <= 0:
                    print('[FaceEngine] Liveness self-test: fake face not detected, trying real face test...')
                    
                    try:
                        from models import get_all_users
                        users = get_all_users()
                        for u in users:
                            if u.get('face_image'):
                                import base64
                                img_data = base64.b64decode(u['face_image'].split(',')[1] if ',' in u['face_image'] else u['face_image'])
                                img_array = np.frombuffer(img_data, dtype=np.uint8)
                                img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                                if img is not None:
                                    w3, h3 = img.shape[1], img.shape[0]
                                    img_ptr3 = img.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))
                                    faces3 = _zero_struct(ASF_MultiFaceInfo)
                                    ret_detect3 = self._lib.ASFDetectFaces(
                                        self._engine, w3, h3, ASVL_PAF_RGB24_B8G8R8,
                                        img_ptr3, ctypes.byref(faces3), ASF_DETECT_MODEL_RGB)
                                    print(f'[FaceEngine] Liveness self-test: real face ASFDetectFaces={ret_detect3}, faces={faces3.faceNum}')
                                    
                                    if ret_detect3 == 0 and faces3.faceNum > 0:
                                        img_data3 = ASF_ImageData()
                                        img_data3.u32PixelArrayFormat = ASVL_PAF_RGB24_B8G8R8
                                        img_data3.i32Width = w3
                                        img_data3.i32Height = h3
                                        img_data3.ppu8Plane[0] = img_ptr3
                                        img_data3.pi32Pitch[0] = w3 * 3
                                        ret_process3 = self._lib.ASFProcessEx(
                                            self._engine, ctypes.byref(img_data3), ctypes.byref(faces3), ASF_LIVENESS)
                                        print(f'[FaceEngine] Liveness self-test: real face ASFProcess={ret_process3}')
                                        
                                        if ret_process3 == 0:
                                            liveness_info3 = _zero_struct(ASF_LivenessInfo)
                                            ret_score3 = self._lib.ASFGetLivenessScore(
                                                self._engine, ctypes.byref(liveness_info3))
                                            print(f'[FaceEngine] Liveness self-test: ASFGetLivenessScore={ret_score3}, num={liveness_info3.num}')
                                            if ret_score3 == 0 and liveness_info3.num > 0:
                                                print('[FaceEngine] Liveness self-test: PASSED with real face')
                                                return True
                                    break
                    except Exception as e:
                        print(f'[FaceEngine] Liveness self-test: real face test error: {e}')

                    return False

                img_data2 = ASF_ImageData()
                img_data2.u32PixelArrayFormat = ASVL_PAF_RGB24_B8G8R8
                img_data2.i32Width = w2
                img_data2.i32Height = h2
                img_data2.ppu8Plane[0] = img_ptr2
                img_data2.pi32Pitch[0] = w2 * 3
                ret_process2 = self._lib.ASFProcessEx(
                    self._engine, ctypes.byref(img_data2), ctypes.byref(faces2), ASF_LIVENESS)
                print(f'[FaceEngine] Liveness self-test: ASFProcess returned {ret_process2}')

                if ret_process2 != 0:
                    return False

                liveness_info2 = _zero_struct(ASF_LivenessInfo)
                ret_score2 = self._lib.ASFGetLivenessScore(
                    self._engine, ctypes.byref(liveness_info2))
                print(f'[FaceEngine] Liveness self-test: ASFGetLivenessScore returned {ret_score2}, num={liveness_info2.num}')
                return ret_score2 == 0

        except Exception as e:
            print(f'[FaceEngine] Liveness self-test error: {e}')
            import traceback
            traceback.print_exc()
            return False

    # ─── 状态查询 ───────────────────────────────

    def is_demo_mode(self):
        return self._demo_mode

    def is_liveness_available(self):
        """活体检测是否真正可用（通过自检验证过）"""
        return not self._demo_mode and self._liveness_available

    # ─── 人脸检测 ───────────────────────────────

    def detect_faces(self, image_data):
        if not self._initialized:
            raise FaceNotInitializedError()
        if self._demo_mode:
            return [{'x': 100, 'y': 100, 'width': 200, 'height': 200, 'score': 0.95}]
        try:
            import cv2
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                print('[FaceEngine] detect_faces: cv2.imdecode returned None')
                return []
            h, w = img.shape[:2]
            img_ptr = img.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))

            faces = _zero_struct(ASF_MultiFaceInfo)
            ret = self._lib.ASFDetectFaces(
                self._engine, w, h, ASVL_PAF_RGB24_B8G8R8,
                img_ptr, ctypes.byref(faces), ASF_DETECT_MODEL_RGB)

            if ret != 0:
                print(f'[FaceEngine] detect_faces: ASFDetectFaces returned {ret}')
                return []
            results = []
            for i in range(faces.faceNum):
                rect = faces.faceRect[i]
                results.append({
                    'x': rect.left, 'y': rect.top,
                    'width': rect.right - rect.left,
                    'height': rect.bottom - rect.top,
                    'score': 0.95,
                })
            return results
        except Exception as e:
            print(f'[FaceEngine] detect_faces error: {e}')
            return []

    # ─── 活体检测 ───────────────────────────────

    def detect_liveness(self, image_data):
        """检测图片中人脸的活体状态 (RGB活体检测)

        Returns:
            list[dict]: 每张人脸的活体检测结果:
                - is_live (bool): 是否活体
                - score (int): SDK原始值 (1=活体, 0=非活体, -1=不确定)
            Demo 模式或活体不可用时返回 [{'is_live': True, 'score': 1}]
        """
        if not self._initialized:
            raise FaceNotInitializedError()

        # Demo 模式或活体不可用 → 直接放行
        if self._demo_mode or not self._liveness_available:
            reason = 'demo' if self._demo_mode else 'liveness_not_available'
            print(f'[FaceEngine] detect_liveness: bypass ({reason})')
            return [{'is_live': True, 'score': 1}]

        try:
            import cv2
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                print('[FaceEngine] detect_liveness: cv2.imdecode returned None')
                return []
            h, w = img.shape[:2]
            img_ptr = img.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))

            # 1. 检测人脸
            faces = _zero_struct(ASF_MultiFaceInfo)
            ret = self._lib.ASFDetectFaces(
                self._engine, w, h, ASVL_PAF_RGB24_B8G8R8,
                img_ptr, ctypes.byref(faces), ASF_DETECT_MODEL_RGB)
            if ret != 0:
                print(f'[FaceEngine] detect_liveness: ASFDetectFaces returned {ret}')
                return []
            if faces.faceNum <= 0:
                print(f'[FaceEngine] detect_liveness: no face detected')
                return []

            print(f'[FaceEngine] detect_liveness: {faces.faceNum} face(s) detected')

            # 2. 处理活体检测 (V5.0 使用 ASFProcessEx)
            img_data = ASF_ImageData()
            img_data.u32PixelArrayFormat = ASVL_PAF_RGB24_B8G8R8
            img_data.i32Width = w
            img_data.i32Height = h
            img_data.ppu8Plane[0] = img_ptr
            img_data.pi32Pitch[0] = w * 3
            ret = self._lib.ASFProcessEx(
                self._engine, ctypes.byref(img_data), ctypes.byref(faces), ASF_LIVENESS)
            if ret != 0:
                print(f'[FaceEngine] detect_liveness: ASFProcess returned {ret} (MAYBE_LIVENESS_UNSUPPORTED={0x27})')
                # 错误码 0x27 (39) = MERR_LIVENESS_UNSUPPORTED
                # 如果是这个错误，说明 SDK 不支持活体检测
                return []

            # 3. 获取活体检测结果
            liveness_info = _zero_struct(ASF_LivenessInfo)
            ret = self._lib.ASFGetLivenessScore(
                self._engine, ctypes.byref(liveness_info))
            if ret != 0:
                print(f'[FaceEngine] detect_liveness: ASFGetLivenessScore returned {ret}')
                return []
            if liveness_info.num <= 0:
                print(f'[FaceEngine] detect_liveness: ASFGetLivenessScore num={liveness_info.num}')
                return []

            results = []
            for i in range(liveness_info.num):
                is_live_val = liveness_info.isLive[i]
                is_live = is_live_val == 1  # 1=real, 0=spoof/photo, negative=error
                print(f'[FaceEngine] detect_liveness: face[{i}] isLive={is_live_val} -> {"LIVE" if is_live else "SPOOF"}')
                results.append({
                    'is_live': is_live,
                    'score': is_live_val,
                })
            return results

        except Exception as e:
            print(f'[FaceEngine] detect_liveness error: {e}')
            import traceback
            traceback.print_exc()
            return []

    def check_liveness(self, image_data):
        """简单活体验证：判断图片中是否存在活体人脸

        Returns:
            bool: True 表示通过 (或 Demo 模式 / 活体不可用)
        """
        results = self.detect_liveness(image_data)
        if not results:
            return False
        return any(r['is_live'] for r in results)

    # ─── 特征提取 ───────────────────────────────

    def extract_feature(self, image_data):
        if not self._initialized:
            raise FaceNotInitializedError()
        if self._demo_mode:
            return hashlib.md5(image_data).digest()
        try:
            import cv2
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return None
            h, w = img.shape[:2]
            img_ptr = img.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))

            # 检测人脸
            faces = _zero_struct(ASF_MultiFaceInfo)
            ret = self._lib.ASFDetectFaces(
                self._engine, w, h, ASVL_PAF_RGB24_B8G8R8,
                img_ptr, ctypes.byref(faces), ASF_DETECT_MODEL_RGB)

            if ret != 0 or faces.faceNum <= 0:
                return None

            # 取第一张人脸
            single = _zero_struct(ASF_SingleFaceInfo)
            if faces.faceNum > 0:
                rect = faces.faceRect[0]
                single.faceRect = MRECT(rect.left, rect.top, rect.right, rect.bottom)
                single.faceOrient = faces.faceOrient[0] if faces.faceOrient else 0
                # V5.0: 必须从 ASFDetectFaces 结果复制 faceDataInfo
                if faces.faceDataInfoList:
                    single.faceDataInfo = faces.faceDataInfoList[0]

            feature = _zero_struct(ASF_FaceFeature)
            ret = self._lib.ASFFaceFeatureExtract(
                self._engine, w, h, ASVL_PAF_RGB24_B8G8R8,
                img_ptr, ctypes.byref(single), 0, 0, ctypes.byref(feature))

            if ret != 0 or not feature.feature:
                return None
            return ctypes.string_at(feature.feature, feature.featureSize)

        except Exception as e:
            print(f'[FaceEngine] extract error: {e}')
            return None


    # ─── 合并方法：一次检测完成活体+特征提取 ─────

    def extract_feature_with_liveness(self, image_data):
        """一次图片解码 + 一次 ASFDetectFaces，同时完成活体检测和特征提取

        返回: (feature_bytes, liveness_result)
            - liveness_result: None 表示未做活体 / [{'is_live': bool, 'score': int}] 表示活体结果
        """
        if not self._initialized:
            raise FaceNotInitializedError()
        if self._demo_mode:
            return hashlib.md5(image_data).digest(), [{'is_live': True, 'score': 1}]
        try:
            import cv2
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return None, None
            h, w = img.shape[:2]
            img_ptr = img.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))

            # 只检测一次人脸
            faces = _zero_struct(ASF_MultiFaceInfo)
            ret = self._lib.ASFDetectFaces(
                self._engine, w, h, ASVL_PAF_RGB24_B8G8R8,
                img_ptr, ctypes.byref(faces), ASF_DETECT_MODEL_RGB)

            if ret != 0 or faces.faceNum <= 0:
                return None, None

            # 复用 faces 结果做活体验证
            liveness_result = None
            if self._liveness_available:
                img_data = ASF_ImageData()
                img_data.u32PixelArrayFormat = ASVL_PAF_RGB24_B8G8R8
                img_data.i32Width = w
                img_data.i32Height = h
                img_data.ppu8Plane[0] = img_ptr
                img_data.pi32Pitch[0] = w * 3
                ret_proc = self._lib.ASFProcessEx(
                    self._engine, ctypes.byref(img_data),
                    ctypes.byref(faces), ASF_LIVENESS)
                if ret_proc == 0:
                    liveness_info = _zero_struct(ASF_LivenessInfo)
                    ret_score = self._lib.ASFGetLivenessScore(
                        self._engine, ctypes.byref(liveness_info))
                    if ret_score == 0 and liveness_info.num > 0:
                        liveness_result = []
                        for i in range(liveness_info.num):
                            is_live_val = liveness_info.isLive[i]
                            liveness_result.append({
                                'is_live': is_live_val == 1,
                                'score': is_live_val,
                            })
                        print(f'[FaceEngine] extract_with_liveness: liveness={liveness_result}')
                    else:
                        liveness_result = [{'is_live': False, 'score': -1}]
                else:
                    print(f'[FaceEngine] extract_with_liveness: ASFProcessEx returned {ret_proc}, bypassing liveness')

            # 复用 faces 结果做特征提取（不再重新检测）
            single = _zero_struct(ASF_SingleFaceInfo)
            rect = faces.faceRect[0]
            single.faceRect = MRECT(rect.left, rect.top, rect.right, rect.bottom)
            single.faceOrient = faces.faceOrient[0] if faces.faceOrient else 0
            if faces.faceDataInfoList:
                single.faceDataInfo = faces.faceDataInfoList[0]

            feature = _zero_struct(ASF_FaceFeature)
            ret = self._lib.ASFFaceFeatureExtract(
                self._engine, w, h, ASVL_PAF_RGB24_B8G8R8,
                img_ptr, ctypes.byref(single), 0, 0, ctypes.byref(feature))

            if ret != 0 or not feature.feature:
                return None, liveness_result
            return ctypes.string_at(feature.feature, feature.featureSize), liveness_result

        except Exception as e:
            print(f'[FaceEngine] extract_with_liveness error: {e}')
            return None, None

    # ─── 人脸特征内存缓存 ───────────────────────

    def get_cached_features(self):
        """从内存缓存读取所有人脸特征，过期自动刷新"""
        import time
        if self._feature_cache is None or (time.time() - self._cache_timestamp) > self._cache_ttl:
            from models import get_all_face_features
            self._feature_cache = get_all_face_features()
            self._cache_timestamp = time.time()
            print(f'[FaceEngine] 缓存刷新: {len(self._feature_cache)} 个特征')
        return self._feature_cache

    def get_cached_user_feature(self, user_id):
        """从缓存中取指定用户的特征"""
        for uid, feat in self.get_cached_features():
            if uid == user_id:
                return feat
        return None

    def invalidate_cache(self):
        """录入/删除人脸时调用，清空缓存"""
        self._feature_cache = None
        self._cache_timestamp = 0
        print('[FaceEngine] 缓存已失效')

    # ─── 特征比对 & 搜索 ─────────────────────────

    def compare_feature(self, f1, f2):
        if self._demo_mode:
            if f1 == f2:
                return 0.95
            if isinstance(f1, bytes) and isinstance(f2, bytes) and len(f1) > 0:
                mlen = min(len(f1), len(f2))
                if mlen == 0:
                    return 0.0
                matches = sum(1 for i in range(mlen) if f1[i] == f2[i])
                return matches / mlen * 0.8
            return 0.3

        if not self._lib or not f1 or not f2:
            return 0.0
        try:
            def make_feat(data):
                feat = ASF_FaceFeature()
                buf = ctypes.create_string_buffer(data)
                feat.feature = ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte))
                feat.featureSize = len(data)
                return feat

            conf = ctypes.c_float()
            ret = self._lib.ASFFaceFeatureCompare(
                self._engine,
                ctypes.byref(make_feat(f1)),
                ctypes.byref(make_feat(f2)),
                ctypes.byref(conf),
                ASF_LIFE_PHOTO,
            )
            return conf.value if ret == 0 else 0.0
        except Exception:
            return 0.0

    def search(self, feature, enrolled, threshold=None):
        if not self._initialized:
            raise FaceNotInitializedError()
        if threshold is None:
            threshold = FACE_RECOGNITION_THRESHOLD
        if not enrolled:
            return None
        best_match = None
        best_score = 0.0
        for uid, feat in enrolled:
            score = self.compare_feature(feature, feat)
            if score > best_score:
                best_score = score
                best_match = uid
        if best_score >= threshold:
            return best_match, best_score
        return None

    # ─── 清理 ───────────────────────────────────

    def uninitialize(self):
        if self._engine and self._lib:
            try:
                self._lib.ASFUninitEngine(self._engine)
            except Exception:
                pass
        self._engine = None
        self._initialized = False

    def __del__(self):
        self.uninitialize()
