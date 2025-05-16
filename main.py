import os
import sys
from app import create_app
from config import SERVER_HOST, SERVER_PORT, DEBUG

# Sử dụng port khác để tránh xung đột với server đang chạy
app = create_app()

if __name__ == "__main__":
    # Sử dụng port 8003 thay vì 8002
    custom_port = 8003
    app.run(host=SERVER_HOST, port=custom_port, debug=DEBUG, single_process=True)
    print(f"API Documentation available at: http://{SERVER_HOST}:{custom_port}/docs")
