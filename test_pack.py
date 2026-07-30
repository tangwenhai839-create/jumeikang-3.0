import ctypes, cv2, numpy as np
from sdk.arcface_engine import FaceEngine, ASF_FaceDataInfo, ASF_FaceFeature, ASF_MultiFaceInfo, MRECT, _zero_struct, ASVL_PAF_RGB24_B8G8R8, ASF_DETECT_MODEL_RGB

e = FaceEngine()
e.initialize()

img = cv2.imread("/root/聚美康正式版2.0/test_face.jpg")
h, w = img.shape[:2]
img = cv2.resize(img, (640, 480))
h, w = img.shape[:2]

ptr = img.ctypes.data_as(ctypes.POINTER(ctypes.c_ubyte))

faces = _zero_struct(ASF_MultiFaceInfo)
ret = e._lib.ASFDetectFaces(e._engine, w, h, ASVL_PAF_RGB24_B8G8R8, ptr, ctypes.byref(faces), ASF_DETECT_MODEL_RGB)
print(f"Detect: ret={ret}, faces={faces.faceNum}")

if faces.faceNum > 0:
    rect = faces.faceRect[0]
    orient = faces.faceOrient[0] if faces.faceOrient else 0
    fdi = faces.faceDataInfoList[0] if faces.faceDataInfoList else None
    
    for pack in [1, 4, 8]:
        class TestSingleFaceInfo(ctypes.Structure):
            _pack_ = pack
            _fields_ = [
                ("faceRect", MRECT),
                ("faceOrient", ctypes.c_int),
                ("faceDataInfo", ASF_FaceDataInfo),
            ]
        
        print(f"\n--- pack={pack}, size={ctypes.sizeof(TestSingleFaceInfo)} ---")
        
        single = _zero_struct(TestSingleFaceInfo)
        single.faceRect = MRECT(rect.left, rect.top, rect.right, rect.bottom)
        single.faceOrient = orient
        if fdi:
            single.faceDataInfo = ASF_FaceDataInfo(fdi.data, fdi.dataSize)
        
        feature = _zero_struct(ASF_FaceFeature)
        e._lib.ASFFaceFeatureExtract.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.POINTER(TestSingleFaceInfo),
            ctypes.POINTER(ASF_FaceFeature)
        ]
        ret2 = e._lib.ASFFaceFeatureExtract(e._engine, w, h, ASVL_PAF_RGB24_B8G8R8, ptr, ctypes.byref(single), ctypes.byref(feature))
        print(f"Extract: ret={ret2}, size={feature.featureSize}")
