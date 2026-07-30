import ctypes, cv2, numpy as np

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

class ASF_ImageData(ctypes.Structure):
    _fields_ = [
        ("u32PixelArrayFormat", ctypes.c_uint32),
        ("i32Width", ctypes.c_int32),
        ("i32Height", ctypes.c_int32),
        ("ppu8Plane", ctypes.POINTER(ctypes.c_ubyte) * 4),
        ("pi32Pitch", ctypes.c_int32 * 4),
    ]

def _zero_struct(cls):
    obj = cls()
    ctypes.memset(ctypes.addressof(obj), 0, ctypes.sizeof(obj))
    return obj

ASVL_PAF_RGB24_B8G8R8 = 0x201
ASF_DETECT_MODEL_RGB = 0x01

lib_engine = ctypes.CDLL("/root/聚美康正式版2.0/sdk/linux/libarcsoft_face_engine.so")

ret = lib_engine.ASFOfflineActivation("/root/聚美康正式版2.0/sdk/linux/X2D11246711W5DZ5.dat".encode("utf-8"))
print(f"Activation: {ret}")

engine = ctypes.c_void_p()
ASF_DETECT_MODE_IMAGE = 0xFFFFFFFF
ASF_OP_0_ONLY = 0x1
ASF_AGE = 0x00000008
ASF_GENDER = 0x00000010
ASF_FACE3DANGLE = 0x00000020
ASF_LIVENESS = 0x00000080
ASF_IR_LIVENESS = 0x00000400
ASF_MASKDETECT = 0x00001000
ASF_FACE_DETECT = 0x00000001
ASF_FACERECOGNITION = 0x00000002
ASF_IMAGEQUALITY = 0x00000200

combined_mask = ASF_FACE_DETECT | ASF_FACERECOGNITION | ASF_LIVENESS | ASF_AGE | ASF_GENDER | ASF_FACE3DANGLE | ASF_MASKDETECT | ASF_IMAGEQUALITY

ASF_REC_LARGE = 0x01
ret = lib_engine.ASFInitEngine(
    ASF_DETECT_MODE_IMAGE,
    ASF_OP_0_ONLY,
    5,
    combined_mask,
    ASF_REC_LARGE,
    ctypes.byref(engine),
)
print(f"InitEngine: {ret}, engine={engine.value}")

img = cv2.imread("/root/聚美康正式版2.0/test_face.jpg")
img = cv2.resize(img, (640, 480))
h, w = img.shape[:2]
ptr = img.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))

faces = _zero_struct(ASF_MultiFaceInfo)
lib_engine.ASFDetectFaces.argtypes = [
    ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ctypes.POINTER(ctypes.c_ubyte), ctypes.POINTER(ASF_MultiFaceInfo), ctypes.c_int
]
ret = lib_engine.ASFDetectFaces(engine, w, h, ASVL_PAF_RGB24_B8G8R8, ptr, ctypes.byref(faces), ASF_DETECT_MODEL_RGB)
print(f"DetectFaces: ret={ret}, faces={faces.faceNum}")

if faces.faceNum > 0:
    rect = faces.faceRect[0]
    fdi = faces.faceDataInfoList[0] if faces.faceDataInfoList else None

    single = _zero_struct(ASF_SingleFaceInfo)
    single.faceRect = MRECT(rect.left, rect.top, rect.right, rect.bottom)
    single.faceOrient = faces.faceOrient[0] if faces.faceOrient else 0
    if fdi:
        single.faceDataInfo = ASF_FaceDataInfo(fdi.data, fdi.dataSize)

    feature = _zero_struct(ASF_FaceFeature)

    lib_engine.ASFFaceFeatureExtract.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.POINTER(ctypes.c_ubyte), ctypes.POINTER(ASF_SingleFaceInfo),
        ctypes.c_int, ctypes.c_int, ctypes.POINTER(ASF_FaceFeature),
    ]
    ret2 = lib_engine.ASFFaceFeatureExtract(
        engine, w, h, ASVL_PAF_RGB24_B8G8R8, ptr, ctypes.byref(single),
        0, 0, ctypes.byref(feature)
    )
    print(f"ASFFaceFeatureExtract: ret={ret2}, featureSize={feature.featureSize}")

    img_data = _zero_struct(ASF_ImageData)
    img_data.u32PixelArrayFormat = ASVL_PAF_RGB24_B8G8R8
    img_data.i32Width = w
    img_data.i32Height = h
    img_data.ppu8Plane[0] = ptr
    img_data.pi32Pitch[0] = w * 3

    lib_engine.ASFFaceFeatureExtractEx.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ASF_ImageData), ctypes.POINTER(ASF_SingleFaceInfo),
        ctypes.c_int, ctypes.c_int, ctypes.POINTER(ASF_FaceFeature),
    ]
    ret3 = lib_engine.ASFFaceFeatureExtractEx(
        engine, ctypes.byref(img_data), ctypes.byref(single), 0, 0, ctypes.byref(feature)
    )
    print(f"ASFFaceFeatureExtractEx: ret={ret3}, featureSize={feature.featureSize}")

    if feature.featureSize > 0 and feature.feature:
        arr = np.ctypeslib.as_array(feature.feature, (feature.featureSize,))
        print(f"Feature sample: {arr[:5]}")
    else:
        print("No feature extracted")
else:
    print("No face detected")
