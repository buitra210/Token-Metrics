import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Etherscan API configuration
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
ETHERSCAN_API_URL = os.getenv("ETHERSCAN_API_URL", "https://api.etherscan.io/api")

# Kiểm tra và hiển thị cảnh báo nếu không có API key
if not ETHERSCAN_API_KEY:
    print("CẢNH BÁO: ETHERSCAN_API_KEY chưa được cấu hình!")
    print("1. Đăng ký API key tại: https://etherscan.io/apis")
    print("2. Tạo file .env trong thư mục root với nội dung:")
    print("   ETHERSCAN_API_KEY=your_api_key_here")
    print("3. Hoặc đặt biến môi trường ETHERSCAN_API_KEY")
    ETHERSCAN_API_KEY = "YourEtherscanApiKeyHere"  # Giá trị mặc định để tránh lỗi null

# MongoDB configuration
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017/")
MONGO_DB = os.getenv("MONGO_DB", "blockchain_metrics")

# Web server configuration
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))  # Mặc định port 8002
DEBUG = os.getenv("DEBUG", "True").lower() == "true"  # Mặc định bật debug mode

# Ethereum node (optional)
ETHEREUM_RPC_URL = os.getenv("ETHEREUM_RPC_URL", "")
