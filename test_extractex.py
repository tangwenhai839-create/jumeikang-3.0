import ctypes, cv2, numpy as np, struct
from sdk.arcface_engine import FaceEngine, ASF_SingleFaceInfo, ASF_FaceFeature, ASF_MultiFaceInfo, ASF_FaceDataInfo, MRECT, _zero_struct, ASVL_PAF_RGB24_B8G8R8, ASF_DETECT_MODEL_RGB

e = FaceEngine()
e.initialize()

img = cv2.imread("/root/聚美康正式版2.0/test_face.jpg")
h, w = img.shape[:2]
# 调整为4的倍数
nw = (w // 4) * 4
nh = (h // 4) * 4
img = cv2.resize(img, (nw, nh))
h, w = img.shape[:2]
print(f"Image: {w}x{h}")

ptr = img.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))

faces = _zero_struct(ASF_MultiFaceInfo)
ret = e._lib.ASFDetectFaces(e._engine, w, h, ASVL_PAF_RGB24_B8G8R8, ptr, ctypes.byref(faces), ASF_DETECT_MODEL_RGB)
print(f"Detect: ret={ret}, faces={faces.faceNum}")

if faces.faceNum > 0:
    single = _zero_struct(ASF_SingleFaceInfo)
    r = faces.faceRect[0]
    single.faceRect = MRECT(r.left, r.top, r.right, r.bottom)
    single.faceOrient = faces.faceOrient[0] if faces.faceOrient else 0
    if faces.faceDataInfoList:
        single.faceDataInfo = faces.faceDataInfoList[0]
    
    feature = _zero_struct(ASF_FaceFeature)
    
    # 方法1: 原始 ASFFaceFeatureExtract
    ret1 = e._lib.ASFFaceFeatureExtract(e._engine, w, h, ASVL_PAF_RGB24_B8G8R8, ptr, ctypes.byref(single), ctypes.byref(feature))
    print(f"Extract: ret={ret1}, size={feature.featureSize}")
    
    # 方法2: ASFFaceFeatureExtractEx (V5.0)
    try:
        class ASF_ImageData(ctypes.Structure):
            _fields_ = [
                ("u32PixelArrayFormat", ctypes.c_uint32),
                ("i32Width", ctypes.c_int),
                ("i32Height", ctypes.c_int),
                ("ppu8Plane", ctypes.c_void_p * 4),
                ("pi32Pitch", ctypes.c_int * 4),
            ]
        
        e._lib.ASFFaceFeatureExtractEx.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(ASF_ImageData),
            ctypes.POINTER(ASF_SingleFaceInfo), ctypes.POINTER(ASF_FaceFeature)
        ]
        e._lib.ASFFaceFeatureExtractEx.restype = ctypes.c_int
        
        img_data = ASF_ImageData()
        img_data.u32PixelArrayFormat = ASVL_PAF_RGB24_B8G8R8
        img_data.i32Width = w
        img_data.i32Height = h
        img_data.ppu8Plane[0] = ctypes.cast(ptr, ctypes.c_void_p).value
        img_data.ppu8Plane[1] = 0
        img_data.ppu8Plane[2] = 0
        img_data.ppu8Plane[3] = 0
        img_data.pi32Pitch[0] = w * 3
        img_data.pi32Pitch[1] = 0
        img_data.pi32Pitch[2] = 0
        img_data.pi32Pitch[3] = 0
        
        feature2 = _zero_struct(ASF_FaceFeature)
        ret2 = e._lib.ASFFaceFeatureExtractEx(e._engine, ctypes.byref(img_data), ctypes.byref(single), ctypes.byref(feature2))
        print(f"ExtractEx: ret={ret2}, size={feature2.featureSize}")
    except Exception as ex:
        print(f"ExtractEx error: {ex}")
