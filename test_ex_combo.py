import ctypes, cv2, numpy as np
from sdk.arcface_engine import FaceEngine, ASF_SingleFaceInfo, ASF_FaceFeature, ASF_MultiFaceInfo, ASF_FaceDataInfo, MRECT, _zero_struct, ASVL_PAF_RGB24_B8G8R8, ASF_DETECT_MODEL_RGB

e = FaceEngine()
e.initialize()

img = cv2.imread("/root/聚美康正式版2.0/test_face.jpg")
h, w = img.shape[:2]
img = cv2.resize(img, (640, 480))
h, w = img.shape[:2]
ptr = img.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))

class ASF_ImageData(ctypes.Structure):
    _fields_ = [
        ("u32PixelArrayFormat", ctypes.c_uint32),
        ("i32Width", ctypes.c_int),
        ("i32Height", ctypes.c_int),
        ("ppu8Plane", ctypes.c_void_p * 4),
        ("pi32Pitch", ctypes.c_int * 4),
    ]

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

print(f"ASF_ImageData size: {ctypes.sizeof(ASF_ImageData)}")

# 测试 ASFDetectFacesEx
faces = _zero_struct(ASF_MultiFaceInfo)
e._lib.ASFDetectFacesEx.argtypes = [ctypes.c_void_p, ctypes.POINTER(ASF_ImageData), ctypes.POINTER(ASF_MultiFaceInfo), ctypes.c_int]
e._lib.ASFDetectFacesEx.restype = ctypes.c_int
ret = e._lib.ASFDetectFacesEx(e._engine, ctypes.byref(img_data), ctypes.byref(faces), ASF_DETECT_MODEL_RGB)
print(f"DetectFacesEx: ret={ret}, faces={faces.faceNum}")

if faces.faceNum > 0:
    rect = faces.faceRect[0]
    orient = faces.faceOrient[0] if faces.faceOrient else 0
    fdi = faces.faceDataInfoList[0] if faces.faceDataInfoList else None
    
    single = _zero_struct(ASF_SingleFaceInfo)
    single.faceRect = MRECT(rect.left, rect.top, rect.right, rect.bottom)
    single.faceOrient = orient
    if fdi:
        single.faceDataInfo = ASF_FaceDataInfo(fdi.data, fdi.dataSize)
    
    feature = _zero_struct(ASF_FaceFeature)
    e._lib.ASFFaceFeatureExtractEx.argtypes = [ctypes.c_void_p, ctypes.POINTER(ASF_ImageData), ctypes.POINTER(ASF_SingleFaceInfo), ctypes.POINTER(ASF_FaceFeature)]
    e._lib.ASFFaceFeatureExtractEx.restype = ctypes.c_int
    ret2 = e._lib.ASFFaceFeatureExtractEx(e._engine, ctypes.byref(img_data), ctypes.byref(single), ctypes.byref(feature))
    print(f"ExtractEx: ret={ret2}, size={feature.featureSize}")
