import ctypes

lib_engine = ctypes.CDLL("/root/聚美康正式版2.0/sdk/linux/libarcsoft_face_engine.so")

ASF_DETECT_MODE_IMAGE = 0xFFFFFFFF
ASF_OP_0_ONLY = 0x1
ASF_REC_LARGE = 0x01

lib_engine.ASFInitEngine.argtypes = [ctypes.c_uint32, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32, ctypes.POINTER(ctypes.c_void_p)]

for mask_val in [0x0005, 0x0085, 0x0015, 0x0205, 0x0405, 0x1005]:
    engine = ctypes.c_void_p()
    ret = lib_engine.ASFInitEngine(ASF_DETECT_MODE_IMAGE, ASF_OP_0_ONLY, 5, mask_val, ASF_REC_LARGE, ctypes.byref(engine))
    print(f"mask=0x{mask_val:04x}: init={ret}, engine={engine.value}")
    if engine.value:
        lib_engine.ASFUninitEngine(engine)
