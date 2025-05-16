# Blockchain Metrics API

API backend cho dự án phân tích các chỉ số blockchain.

## Cài đặt

1. Clone repository

```bash
git clone <repository-url>
cd blockchain-metrics/backend
```

2. Cài đặt các dependencies

```bash
pip install -r requirements.txt
```

3. Tạo tệp .env trong thư mục root với cấu hình:

```
ETHERSCAN_API_KEY=your_api_key_here
ETHERSCAN_API_URL=https://api.etherscan.io/api
MONGO_URL=mongodb://localhost:27017/
MONGO_DB=blockchain_metrics
SERVER_HOST=0.0.0.0
SERVER_PORT=8002
DEBUG=True
```

## Cấu hình API key Etherscan

Để sử dụng đầy đủ chức năng của ứng dụng, bạn cần một API key từ Etherscan:

1. Đăng ký tài khoản tại [Etherscan](https://etherscan.io)
2. Đăng nhập và truy cập [trang API Keys](https://etherscan.io/myapikey)
3. Tạo API key mới và copy vào tệp .env

## Khởi chạy server

```bash
python main.py
```

Server sẽ chạy tại địa chỉ http://0.0.0.0:8002

## API Endpoints

### Swagger UI

Truy cập tài liệu API tại: http://0.0.0.0:8002/docs

### Chức năng chính

1. **Lấy metrics cho một campaign**

   - Endpoint: `GET /api/metrics/<campaign_id>`
   - Query params: `from_date`, `to_date` (optional, định dạng ISO)

2. **Lấy metrics từ Etherscan**
   - Endpoint: `POST /api/etherscan/fetch-metrics`
   - Request body:
   ```json
   {
     "contractAddress": "0xbc7f459eE26D2F83d20Da97FCF0Eb5467B3E28a7",
     "fromDate": "2023-01-01T00:00:00Z",
     "toDate": "2023-12-31T23:59:59Z"
   }
   ```

## Xử lý lỗi thường gặp

1. **"ETHERSCAN_API_KEY chưa được cấu hình"**

   - Bạn cần tạo tệp .env với API key hợp lệ từ Etherscan.

2. **"Etherscan API Error: NOTOK"**

   - API key không hợp lệ hoặc đã vượt quá rate limit
   - Vui lòng kiểm tra cấu hình hoặc thử lại sau

3. **"Error fetching metrics: Failed when parsing body as json"**
   - Request body không đúng định dạng JSON
   - Đảm bảo content-type là application/json
