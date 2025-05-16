import os
import sys
from app import create_app
from config import SERVER_HOST, SERVER_PORT, DEBUG

app = create_app()

if __name__ == "__main__":
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=DEBUG, single_process=True)
    print(f"API Documentation available at: http://{SERVER_HOST}:{SERVER_PORT}/docs")
