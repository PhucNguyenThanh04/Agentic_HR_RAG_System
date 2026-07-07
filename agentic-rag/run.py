import uvicorn
from src.core.settings import get_settings

settings = get_settings()

if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level="debug" if settings.api_debug else "info",
    )