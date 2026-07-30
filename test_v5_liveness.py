import ctypes, cv2

class MRECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_int), ("top", ctypes.c_int),
                ("right", ctypes.c_int), ("bottom", ctypes.c_int)]

class ASF_FaceDataInfo(ctypes.Structure):
    _fields_ = [("data", ctypes.c_void_p), ("dataSize", ctypes.c_int)]

class ASF_SingleFaceInfo(ctypes.Structure):
    _fields_ = [
        ("faceRect", MRECT),
        ("faceOrient", ctypes.c_int),
        ("faceDataInfo", ASF_FaceDataInfo),
    ]

class ASF_MultiFaceInfo(ctypes.Structure):
    _fields_ = [
        ("faceNum", ctypes.c_int),
        ("faceRect", ctypes.POINTER(MRECT)),
        ("faceOrient", ctypes.POINTER(ctypes.c_int)),
        ("faceID", ctypes.POINTER(ctypes.c_int)),
        ("faceDataInfoList", ctypes.POINTER(ASF_FaceDataInfo)),
        ("faceIsWithinBoundary", ctypes.POINTER(ctypes.c_int)),
        ("foreheadRect", ctypes.POINTER(MRECT)),
        ("face3DAngleInfo", ctypes.c_void_p),
    ]

class ASF_FaceFeature(ctypes.Structure):
    _fields_ = [("feature", ctypes.POINTER(ctypes.c_float)), ("featureSize", ctypes.c_int)]

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

ret = lib_engine.ASFOfflineActivation("/root/聚美康正式版2.0/sdk/linux/X2D11246711W5DZ5.dat".encode("utf-8"))
print(f"Activation: {ret}")

lib_engine.ASFInitEngine.argtypes = [ctypes.c_uint32, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32, ctypes.POINTER(ctypes.c_void_p)]

for mask_val in [0x0005, 0x0085]:
    engine = ctypes.c_void_p()
    ret = lib_engine.ASFInitEngine(ASF_DETECT_MODE_IMAGE, ASF_OP_0_ONLY, 5, mask_val, ASF_REC_LARGE, ctypes.byref(engine))
    print(f"\nmask=0x{mask_val:04x}: init={ret}, engine={engine.value}")
    
    if engine.value:
        img = cv2.imread("/root/聚美康正式版2.0/test_face.jpg")
        img = cv2.resize(img, (640, 480))
        h, w = img.shape[:2]
        ptr = img.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))
        faces = _zero_struct(ASF_MultiFaceInfo)
        lib_engine.ASFDetectFaces.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.POINTER(ctypes.c_ubyte), ctypes.POINTER(ASF_MultiFaceInfo), ctypes.c_int]
        ret2 = lib_engine.ASFDetectFaces(engine, w, h, ASVL_PAF_RGB24_B8G8R8, ptr, ctypes.byref(faces), ASF_DETECT_MODEL_RGB)
        print(f"  Detect: ret={ret2}, faces={faces.faceNum}")
        
        if faces.faceNum > 0:
            # Test liveness
            ret3 = lib_engine.ASFProcess(engine, w, h, ASVL_PAF_RGB24_B8G8R8, ptr, ctypes.byref(faces), ASF_LIVENESS)
            print(f"  Liveness Process: ret={ret3}")
            if ret3 == 0:
                class ASF_LivenessInfo(ctypes.Structure):
                    _fields_ = [("isLive", ctypes.POINTER(ctypes.c_int)), ("num", ctypes.c_int)]
                liveness = _zero_struct(ASF_LivenessInfo)
                ret4 = lib_engine.ASFGetLivenessScore(engine, ctypes.byref(liveness))
                print(f"  Liveness Score: ret={ret4}, num={liveness.num}")
            
            # Test feature extract
            single = _zero_struct(ASF_SingleFaceInfo)
            single.faceRect = faces.faceRect[0]
            single.faceOrient = faces.faceOrient[0]
            if faces.faceDataInfoList:
                single.faceDataInfo = faces.faceDataInfoList[0]
            feature = _zero_struct(ASF_FaceFeature)
            lib_engine.ASFFaceFeatureExtract.argtypes = [
                ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                ctypes.POINTER(ctypes.c_ubyte), ctypes.POINTER(ASF_SingleFaceInfo),
                ctypes.c_int, ctypes.c_int, ctypes.POINTER(ASF_FaceFeature),
            ]
            ret5 = lib_engine.ASFFaceFeatureExtract(engine, w, h, ASVL_PAF_RGB24_B8G8R8, ptr, ctypes.byref(single), 0, 0, ctypes.byref(feature))
            print(f"  Feature: ret={ret5}, size={feature.featureSize}")
        
        lib_engine.ASFUninitEngine(engine)
