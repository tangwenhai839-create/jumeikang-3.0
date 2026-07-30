import ctypes, cv2, numpy as np
from sdk.arcface_engine import FaceEngine, ASF_SingleFaceInfo, ASF_FaceFeature, ASF_MultiFaceInfo, ASF_FaceDataInfo, MRECT, _zero_struct, ASVL_PAF_RGB24_B8G8R8, ASF_DETECT_MODEL_RGB

e = FaceEngine()
e.initialize()

img = cv2.imread("/root/聚美康正式版2.0/test_face.jpg")
img = cv2.resize(img, (640, 480))
h, w = img.shape[:2]
ptr = img.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))

faces = _zero_struct(ASF_MultiFaceInfo)
ret = e._lib.ASFDetectFaces(e._engine, w, h, ASVL_PAF_RGB24_B8G8R8, ptr, ctypes.byref(faces), ASF_DETECT_MODEL_RGB)

if faces.faceNum > 0:
    rect = faces.faceRect[0]
    fdi = faces.faceDataInfoList[0] if faces.faceDataInfoList else None
    
    for orient in [0, 1, 2, 3, 4, 5]:
        single = _zero_struct(ASF_SingleFaceInfo)
        single.faceRect = MRECT(rect.left, rect.top, rect.right, rect.bottom)
        single.faceOrient = orient
        if fdi:
            single.faceDataInfo = ASF_FaceDataInfo(fdi.data, fdi.dataSize)
        
        feature = _zero_struct(ASF_FaceFeature)
        e._lib.ASFFaceFeatureExtract.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.POINTER(ASF_SingleFaceInfo),
            ctypes.POINTER(ASF_FaceFeature)
        ]
        ret2 = e._lib.ASFFaceFeatureExtract(e._engine, w, h, ASVL_PAF_RGB24_B8G8R8, ptr, ctypes.byref(single), ctypes.byref(feature))
        print(f"orient={orient}: ret={ret2}, size={feature.featureSize}")
