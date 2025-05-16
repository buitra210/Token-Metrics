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

## Khởi chạy server

```bash
python main.py
```

Server sẽ chạy tại địa chỉ http://0.0.0.0:8002

## API Endpoints

### Swagger UI

Truy cập tài liệu API tại: http://0.0.0.0:8000/docs

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
