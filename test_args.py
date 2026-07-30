import ctypes, cv2, numpy as np
from sdk.arcface_engine import FaceEngine, ASF_SingleFaceInfo, ASF_FaceFeature, ASF_MultiFaceInfo, ASF_FaceDataInfo, MRECT, _zero_struct, ASVL_PAF_RGB24_B8G8R8, ASF_DETECT_MODEL_RGB

e = FaceEngine()
e.initialize()

img = cv2.imread("/root/聚美康正式版2.0/test_face.jpg")
h, w = img.shape[:2]
img = cv2.resize(img, (640, 480))
h, w = img.shape[:2]
ptr = img.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))

faces = _zero_struct(ASF_MultiFaceInfo)
ret = e._lib.ASFDetectFaces(e._engine, w, h, ASVL_PAF_RGB24_B8G8R8, ptr, ctypes.byref(faces), ASF_DETECT_MODEL_RGB)

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
    
    # 尝试1: 3个参数 (hEngine, faceInfo, feature)
    e._lib.ASFFaceFeatureExtract.argtypes = [ctypes.c_void_p, ctypes.POINTER(ASF_SingleFaceInfo), ctypes.POINTER(ASF_FaceFeature)]
    ret1 = e._lib.ASFFaceFeatureExtract(e._engine, ctypes.byref(single), ctypes.byref(feature))
    print(f"3 args: ret={ret1}, size={feature.featureSize}")
    
    # 尝试2: 3个参数，但faceDataInfo指向原始图像数据
    single2 = _zero_struct(ASF_SingleFaceInfo)
    single2.faceRect = MRECT(rect.left, rect.top, rect.right, rect.bottom)
    single2.faceOrient = orient
    single2.faceDataInfo.data = ctypes.cast(ptr, ctypes.c_void_p).value
    single2.faceDataInfo.dataSize = w * h * 3
    feature2 = _zero_struct(ASF_FaceFeature)
    ret2 = e._lib.ASFFaceFeatureExtract(e._engine, ctypes.byref(single2), ctypes.byref(feature2))
    print(f"3 args (raw img): ret={ret2}, size={feature2.featureSize}")
    
    # 尝试3: 7个参数，但argtypes移除
    e._lib.ASFFaceFeatureExtract.argtypes = None
    feature3 = _zero_struct(ASF_FaceFeature)
    ret3 = e._lib.ASFFaceFeatureExtract(e._engine, w, h, ASVL_PAF_RGB24_B8G8R8, ptr, ctypes.byref(single), ctypes.byref(feature3))
    print(f"7 args (no argtypes): ret={ret3}, size={feature3.featureSize}")
