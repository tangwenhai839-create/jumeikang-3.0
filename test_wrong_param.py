import ctypes, cv2

class MRECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_int), ("top", ctypes.c_int),
                ("right", ctypes.c_int), ("bottom", ctypes.c_int)]

class ASF_MultiFaceInfo(ctypes.Structure):
    _fields_ = [("faceNum", ctypes.c_int), ("faceRect", ctypes.POINTER(MRECT)),
                ("faceOrient", ctypes.POINTER(ctypes.c_int)), ("faceID", ctypes.POINTER(ctypes.c_int)),
                ("faceDataInfoList", ctypes.POINTER(ctypes.c_void_p)),
                ("faceIsWithinBoundary", ctypes.POINTER(ctypes.c_int)),
                ("foreheadRect", ctypes.POINTER(MRECT)), ("face3DAngleInfo", ctypes.c_void_p)]

class ASF_LivenessInfo(ctypes.Structure):
    _fields_ = [("isLive", ctypes.POINTER(ctypes.c_int)), ("num", ctypes.c_int), ("faceID", ctypes.POINTER(ctypes.c_int))]

def _zero_struct(cls):
    obj = cls()
    ctypes.memset(ctypes.addressof(obj), 0, ctypes.sizeof(obj))
    return obj

ASVL_PAF_RGB24_B8G8R8 = 0x201
ASF_DETECT_MODEL_RGB = 0x01
ASF_DETECT_MODE_IMAGE = 0xFFFFFFFF
ASF_OP_0_ONLY = 0x1
ASF_REC_LARGE = 0x01
ASF_LIVENESS = 0x00000080

lib_engine = ctypes.CDLL("/root/聚美康正式版2.0/sdk/linux/libarcsoft_face_engine.so")
lib_engine.ASFOfflineActivation("/root/聚美康正式版2.0/sdk/linux/X2D11246711W5DZ5.dat".encode("utf-8"))
engine = ctypes.c_void_p()
lib_engine.ASFInitEngine(ASF_DETECT_MODE_IMAGE, ASF_OP_0_ONLY, 5, 0x0085, ASF_REC_LARGE, ctypes.byref(engine))

img = cv2.imread("/root/聚美康正式版2.0/test_face.jpg")
img = cv2.resize(img, (640, 480))
h, w = img.shape[:2]
ptr = img.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))
faces = _zero_struct(ASF_MultiFaceInfo)
lib_engine.ASFDetectFaces(engine, w, h, ASVL_PAF_RGB24_B8G8R8, ptr, ctypes.byref(faces), ASF_DETECT_MODEL_RGB)

if faces.faceNum > 0:
    # WRONG: pass by value (current code bug)
    lib_engine.ASFSetLivenessParam.argtypes = [ctypes.c_void_p, ctypes.c_float]
    lib_engine.ASFSetLivenessParam(engine, ctypes.c_float(0.0))
    
    ret = lib_engine.ASFProcess(engine, w, h, ASVL_PAF_RGB24_B8G8R8, ptr, ctypes.byref(faces), ASF_LIVENESS)
    liveness = _zero_struct(ASF_LivenessInfo)
    lib_engine.ASFGetLivenessScore(engine, ctypes.byref(liveness))
    print(f"WRONG value pass (0.0): ASFProcess ret={ret}, isLive={liveness.isLive[0] if liveness.isLive and liveness.num > 0 else 'N/A'}")
    
    # CORRECT: pass by pointer
    lib_engine.ASFSetLivenessParam.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float)]
    threshold = ctypes.c_float(0.5)
    lib_engine.ASFSetLivenessParam(engine, ctypes.byref(threshold))
    
    ret2 = lib_engine.ASFProcess(engine, w, h, ASVL_PAF_RGB24_B8G8R8, ptr, ctypes.byref(faces), ASF_LIVENESS)
    liveness2 = _zero_struct(ASF_LivenessInfo)
    lib_engine.ASFGetLivenessScore(engine, ctypes.byref(liveness2))
    print(f"CORRECT pointer pass (0.5): ASFProcess ret={ret2}, isLive={liveness2.isLive[0] if liveness2.isLive and liveness2.num > 0 else 'N/A'}")

lib_engine.ASFUninitEngine(engine)
