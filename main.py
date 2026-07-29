"""
marketplace_seller_platform — main.py
Ponto de entrada da plataforma.
"""
import sys
import uvicorn
from config.settings import API_HOST, API_PORT, APP_NAME, APP_VERSION, ENV
from config.logging_config import setup_logging

log = setup_logging("main")


def main():
    log.info(f"Iniciando {APP_NAME} v{APP_VERSION}")
    log.info(f"Docs: http://{API_HOST}:{API_PORT}/docs")

    uvicorn.run(
        "ui.api:app",
        host=API_HOST,
        port=API_PORT,
        reload=(ENV != "production"),
        log_level="info",
    )


if __name__ == "__main__":
    main()
