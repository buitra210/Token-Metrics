from sanic import Blueprint, response
from sanic.request import Request
from datetime import datetime
from app.services.etherscan_service import EtherscanService
from app.services.db_service import DBService
from pydantic import BaseModel, Field
from sanic_ext import openapi

# Tạo Pydantic model cho request body
class FetchMetricsRequest(BaseModel):
    contractAddress: str = Field(..., description="Ethereum contract address for the token")
    fromDate: str = Field(None, description="Start date for metrics calculation (ISO format)")
    toDate: str = Field(None, description="End date for metrics calculation (ISO format)")

etherscan_blueprint = Blueprint('etherscan', url_prefix='/api/etherscan')

@etherscan_blueprint.route("/fetch-metrics", methods=["POST"])
@openapi.summary("Fetch metrics from Etherscan")
@openapi.description("Calculate token metrics from Etherscan data for a given contract address")
@openapi.body({
    "contractAddress": "0xbc7f459eE26D2F83d20Da97FCF0Eb5467B3E28a7",
    "fromDate": "2023-01-01T00:00:00Z",
    "toDate": "2023-12-31T23:59:59Z"
})
@openapi.response(200, {"success": True, "message": "Token metrics fetched successfully", "data": {}}, "Success")
@openapi.response(400, {"success": False, "message": "Invalid parameters"}, "Invalid parameters")
@openapi.response(500, {"success": False, "message": "Error fetching metrics"}, "Server error")
async def fetch_metrics(request: Request):
    """
    Fetch metrics from Etherscan for a token

    Example request body:
    ```json
    {
        "contractAddress": "0xbc7f459eE26D2F83d20Da97FCF0Eb5467B3E28a7",
        "fromDate": "2023-01-01T00:00:00Z",
        "toDate": "2023-12-31T23:59:59Z"
    }
    ```
    """
    try:
        # Validate request body with Pydantic
        if not request.json:
            return response.json({
                "success": False,
                "message": "Request body is required"
            }, status=400)

        try:
            # Validate với Pydantic
            body = FetchMetricsRequest(**request.json)
        except Exception as e:
            return response.json({
                "success": False,
                "message": f"Invalid request data: {str(e)}"
            }, status=400)

        # Kiểm tra địa chỉ Ethereum
        contract_address = body.contractAddress
        if not contract_address.startswith('0x') or len(contract_address) != 42:
            return response.json({
                "success": False,
                "message": f"Invalid Ethereum address format: {contract_address}. Address must be in format 0x... and 42 characters long."
            }, status=400)

        # Parse optional dates
        from_date = None
        if body.fromDate:
            try:
                from_date = datetime.fromisoformat(body.fromDate.replace('Z', '+00:00'))
            except ValueError:
                return response.json({
                    "success": False,
                    "message": "Invalid fromDate format. Use ISO format (e.g. 2023-01-01T00:00:00Z)"
                }, status=400)

        to_date = None
        if body.toDate:
            try:
                to_date = datetime.fromisoformat(body.toDate.replace('Z', '+00:00'))
            except ValueError:
                return response.json({
                    "success": False,
                    "message": "Invalid toDate format. Use ISO format (e.g. 2023-01-01T00:00:00Z)"
                }, status=400)

        # Mặc định nếu không truyền thì lấy đầu tháng và hiện tại
        if not from_date:
            from_date = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if not to_date:
            to_date = datetime.now()

        # Tính metrics và lưu db
        etherscan_service = EtherscanService()
        metrics = await etherscan_service.calculate_metrics(contract_address, from_date, to_date)

        db_service = DBService(request.app.ctx.db)
        await db_service.store_metrics(metrics)

        return response.json({
            "success": True,
            "message": "Token metrics fetched successfully",
            "data": metrics
        })

    except ValueError as ve:
        return response.json({"success": False, "message": str(ve)}, status=400)
    except Exception as e:
        return response.json({
            "success": False,
            "message": f"Error fetching metrics: {e}"
        }, status=500)

