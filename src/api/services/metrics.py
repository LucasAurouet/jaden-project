from src.api.services.system import get_system_metrics
from src.api.services.inference import get_llama_metrics_from_api

def get_full_system_status():
    return {
        "system": get_system_metrics(),
        "inference": get_llama_metrics_from_api()
    }