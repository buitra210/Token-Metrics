import os
import sys
import logging
from app import create_app
from config import SERVER_HOST, SERVER_PORT, DEBUG

# Configure logging
logging.basicConfig(
    level=logging.INFO if DEBUG else logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

app = create_app()

if __name__ == "__main__":
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=DEBUG, single_process=True)
    print(f"API Documentation available at: http://{SERVER_HOST}:{SERVER_PORT}/docs")
