import ctypes, cv2, numpy as np
from sdk.arcface_engine import FaceEngine, ASF_SingleFaceInfo, ASF_FaceFeature, ASF_MultiFaceInfo, MRECT, _zero_struct, ASVL_PAF_RGB24_B8G8R8, ASF_DETECT_MODEL_RGB

e = FaceEngine()
e.initialize()

img = cv2.imread("/root/聚美康正式版2.0/test_face.jpg")
h, w = img.shape[:2]
nw = (w // 4) * 4
nh = (h // 4) * 4
img = cv2.resize(img, (nw, nh))
h, w = img.shape[:2]
print(f"Resized: {w}x{h}")

ptr = img.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))
faces = _zero_struct(ASF_MultiFaceInfo)
ret = e._lib.ASFDetectFaces(e._engine, w, h, ASVL_PAF_RGB24_B8G8R8, ptr, ctypes.byref(faces), ASF_DETECT_MODEL_RGB)
print(f"Detect: ret={ret}, faces={faces.faceNum}")

if faces.faceNum > 0:
    s = _zero_struct(ASF_SingleFaceInfo)
    r = faces.faceRect[0]
    s.faceRect = MRECT(r.left, r.top, r.right, r.bottom)
    s.faceOrient = faces.faceOrient[0] if faces.faceOrient else 0
    if faces.faceDataInfoList:
        s.faceDataInfo = faces.faceDataInfoList[0]
    f = _zero_struct(ASF_FaceFeature)
    ret2 = e._lib.ASFFaceFeatureExtract(e._engine, w, h, ASVL_PAF_RGB24_B8G8R8, ptr, ctypes.byref(s), ctypes.byref(f))
    print(f"Extract: ret={ret2}, size={f.featureSize}")
