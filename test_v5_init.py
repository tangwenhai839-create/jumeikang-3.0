import ctypes

lib_engine = ctypes.CDLL("/root/聚美康正式版2.0/sdk/linux/libarcsoft_face_engine.so")

ret = lib_engine.ASFOfflineActivation("/root/聚美康正式版2.0/sdk/linux/X2D11246711W5DZ5.dat".encode("utf-8"))
print(f"Activation: {ret}")

ASF_DETECT_MODE_IMAGE = 0xFFFFFFFF
ASF_OP_0_ONLY = 0x1
ASF_FACE_DETECT = 0x00000001
ASF_FACERECOGNITION = 0x00000002

ASF_REC_LARGE = 0x01

# Try 5-parameter call (V3.0 style)
engine = ctypes.c_void_p()
lib_engine.ASFInitEngine.argtypes = [ctypes.c_uint32, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32, ctypes.POINTER(ctypes.c_void_p)]
ret = lib_engine.ASFInitEngine(ASF_DETECT_MODE_IMAGE, ASF_OP_0_ONLY, 5, ASF_FACE_DETECT | ASF_FACERECOGNITION, ctypes.byref(engine))
print(f"InitEngine(5 params): ret={ret}, engine={engine.value}")

# Try 6-parameter call (V5.0 style with recModel at position 5)
engine2 = ctypes.c_void_p()
lib_engine.ASFInitEngine.argtypes = [ctypes.c_uint32, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32, ctypes.POINTER(ctypes.c_void_p)]
ret = lib_engine.ASFInitEngine(ASF_DETECT_MODE_IMAGE, ASF_OP_0_ONLY, 5, ASF_FACE_DETECT | ASF_FACERECOGNITION, ASF_REC_LARGE, ctypes.byref(engine2))
print(f"InitEngine(6 params): ret={ret}, engine={engine2.value}")

# Try 6-parameter call with recModel at position 4
engine3 = ctypes.c_void_p()
lib_engine.ASFInitEngine.argtypes = [ctypes.c_uint32, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32, ctypes.POINTER(ctypes.c_void_p)]
ret = lib_engine.ASFInitEngine(ASF_DETECT_MODE_IMAGE, ASF_OP_0_ONLY, 5, ASF_REC_LARGE, ASF_FACE_DETECT | ASF_FACERECOGNITION, ctypes.byref(engine3))
print(f"InitEngine(6 params recModel=4): ret={ret}, engine={engine3.value}")

# Try 6-parameter call with combinedMask=0
engine4 = ctypes.c_void_p()
ret = lib_engine.ASFInitEngine(ASF_DETECT_MODE_IMAGE, ASF_OP_0_ONLY, 5, 0, ASF_REC_LARGE, ctypes.byref(engine4))
print(f"InitEngine(6 params mask=0): ret={ret}, engine={engine4.value}")

# Try 6-parameter call with combinedMask=0 and recModel at position 4
engine5 = ctypes.c_void_p()
ret = lib_engine.ASFInitEngine(ASF_DETECT_MODE_IMAGE, ASF_OP_0_ONLY, 5, ASF_REC_LARGE, 0, ctypes.byref(engine5))
print(f"InitEngine(6 params recModel=4 mask=0): ret={ret}, engine={engine5.value}")
