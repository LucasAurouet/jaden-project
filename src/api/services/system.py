import time
import psutil

START_TIME = time.time()

try:
    import pynvml
    pynvml.nvmlInit()
    NVML_AVAILABLE = True
    print("NVML library loaded successfully.")
except Exception as e:
    NVML_AVAILABLE = False
    print(f"NVML library not available. GPU metrics will not be collected. ({e})")


def get_system_metrics() -> dict:
    mem = psutil.virtual_memory()

    result = {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "ram_used_gb": round(mem.used / 1024**3, 2),
        "ram_total_gb": round(mem.total / 1024**3, 2),
        "ram_percent": mem.percent,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "gpu_vram_used_mb": None,
        "gpu_vram_total_mb": None,
        "gpu_percent": None,
        "gpu_temp_c": None,
    }

    if NVML_AVAILABLE:
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            result["gpu_vram_used_mb"] = round(info.used / 1024**2, 1)
            result["gpu_vram_total_mb"] = round(info.total / 1024**2, 1)
            result["gpu_temp_c"] = pynvml.nvmlDeviceGetTemperature(
                handle, pynvml.NVML_TEMPERATURE_GPU
            )
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            result["gpu_percent"] = util.gpu
        except Exception:
            pass 

    return result