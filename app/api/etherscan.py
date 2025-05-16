from sanic import Blueprint, response
from sanic.request import Request
from datetime import datetime, timedelta
from app.services.etherscan_service import EtherscanService
from app.services.db_service import DBService
from pydantic import BaseModel, Field
from sanic_ext import openapi
from typing import Optional

# Tạo Pydantic model cho request body
class FetchMetricsRequest(BaseModel):
    contractAddress: str = Field(..., description="Ethereum contract address for the token")
    fromDate: str = Field(None, description="Start date for metrics calculation (ISO format)")
    toDate: str = Field(None, description="End date for metrics calculation (ISO format)")
    maxPages: int = Field(10, description="Maximum number of pages to fetch (0 for unlimited)")
    sortOrder: str = Field("desc", description="Sort order: 'asc' for oldest first, 'desc' for newest first (default)")

# Model for campaign report requests
class CampaignReportRequest(BaseModel):
    contractAddress: str = Field(..., description="Token contract address")
    preCampaignStart: str = Field(..., description="Pre-campaign period start date (ISO format)")
    preCampaignEnd: str = Field(..., description="Pre-campaign period end date (ISO format)")
    campaignStart: str = Field(..., description="Campaign period start date (ISO format)")
    campaignEnd: str = Field(..., description="Campaign period end date (ISO format)")
    maxPages: int = Field(10, description="Maximum pages per period (0 for unlimited)")

etherscan_blueprint = Blueprint('etherscan', url_prefix='/api/etherscan')

@etherscan_blueprint.route("/check-transactions/<contract_address:str>", methods=["GET"])
@openapi.summary("Debug contract transactions")
@openapi.description("Check raw transactions for a contract to help debug issues")
@openapi.parameter("contract_address", str, "Ethereum contract address", required=True)
@openapi.parameter("max_pages", int, "Maximum number of pages to fetch (default: 3)", required=False)
@openapi.parameter("sort_order", str, "Sort order: 'asc' for oldest first, 'desc' for newest first (default: desc)", required=False)
@openapi.response(200, {"success": True, "data": {}}, "Success")
@openapi.response(400, {"success": False, "message": "Invalid address"}, "Invalid parameters")
@openapi.response(500, {"success": False, "message": "Error fetching data"}, "Server error")
async def check_transactions(request: Request, contract_address: str):
    """
    Debugging endpoint to check raw transactions from Etherscan for a contract
    """
    try:
        # Kiểm tra địa chỉ Ethereum
        if not contract_address.startswith('0x') or len(contract_address) != 42:
            return response.json({
                "success": False,
                "message": f"Invalid Ethereum address format: {contract_address}. Address must be in format 0x... and 42 characters long."
            }, status=400)

        # Get pagination parameters
        max_pages = int(request.args.get('max_pages', 3))  # Default 3 pages
        sort_order = request.args.get('sort_order', 'desc')  # Default newest first

        etherscan_service = EtherscanService()
        # Get transactions from the last 365 days to check activity
        from_date = datetime.now() - timedelta(days=365)
        to_date = datetime.now()

        # Get block numbers for timestamp range
        from_block = await etherscan_service.get_block_by_timestamp(int(from_date.timestamp()))
        to_block = await etherscan_service.get_block_by_timestamp(int(to_date.timestamp()))

        transactions = await etherscan_service.get_token_transactions_by_blocks(
            contract_address,
            from_block,
            to_block,
            max_pages=max_pages,
            sort_order=sort_order
        )

        token_info = await etherscan_service.get_token_info(contract_address)

        # Get first few and last few transactions for debugging
        sample_transactions = []
        if len(transactions) > 0:
            # Get up to 5 first and 5 last transactions
            sample_size = min(5, len(transactions))
            first_txs = transactions[:sample_size]
            last_txs = transactions[-sample_size:] if len(transactions) > sample_size else []
            sample_transactions = first_txs + (last_txs if last_txs != first_txs else [])

        return response.json({
            "success": True,
            "data": {
                "contractAddress": contract_address,
                "tokenInfo": token_info,
                "transactionCount": len(transactions),
                "blockRange": {
                    "fromBlock": from_block,
                    "toBlock": to_block
                },
                "dateRange": {
                    "from": from_date.isoformat(),
                    "to": to_date.isoformat()
                },
                "paginationUsed": {
                    "maxPages": max_pages,
                    "sortOrder": sort_order
                },
                "sampleTransactions": sample_transactions[:10]  # Limit to 10 samples
            }
        })

    except Exception as e:
        return response.json({
            "success": False,
            "message": f"Error checking transactions: {str(e)}"
        }, status=500)

@etherscan_blueprint.route("/campaign-report", methods=["POST"])
@openapi.summary("Generate Campaign Report")
@openapi.description("Generate a comprehensive report comparing metrics before and during a campaign period")
@openapi.body({
    "contractAddress": "0x95aD61b0a150d79219dCF64E1E6Cc01f0B64C4cE", # SHIB token as example
    "preCampaignStart": "2023-01-01T00:00:00Z",
    "preCampaignEnd": "2023-01-31T23:59:59Z",
    "campaignStart": "2023-02-01T00:00:00Z",
    "campaignEnd": "2023-02-28T23:59:59Z",
    "maxPages": 10
})
@openapi.response(200, {"success": True, "message": "Campaign report generated successfully", "data": {}}, "Success")
@openapi.response(400, {"success": False, "message": "Invalid parameters"}, "Invalid parameters")
@openapi.response(500, {"success": False, "message": "Error generating report"}, "Server error")
async def campaign_report(request: Request):
    """
    Generate a comprehensive campaign report with pre vs. during campaign metrics comparison
    """
    try:
        # Validate request body
        if not request.json:
            return response.json({
                "success": False,
                "message": "Request body is required"
            }, status=400)

        try:
            body = CampaignReportRequest(**request.json)
        except Exception as e:
            return response.json({
                "success": False,
                "message": f"Invalid request data: {str(e)}"
            }, status=400)

        # Validate contract address
        contract_address = body.contractAddress
        if not contract_address.startswith('0x') or len(contract_address) != 42:
            return response.json({
                "success": False,
                "message": f"Invalid Ethereum address format: {contract_address}. Address must be in format 0x... and 42 characters long."
            }, status=400)

        # Parse dates
        try:
            pre_start = datetime.fromisoformat(body.preCampaignStart.replace('Z', '+00:00'))
            pre_end = datetime.fromisoformat(body.preCampaignEnd.replace('Z', '+00:00'))
            campaign_start = datetime.fromisoformat(body.campaignStart.replace('Z', '+00:00'))
            campaign_end = datetime.fromisoformat(body.campaignEnd.replace('Z', '+00:00'))
        except ValueError as e:
            return response.json({
                "success": False,
                "message": f"Invalid date format. Use ISO format (e.g. 2023-01-01T00:00:00Z): {str(e)}"
            }, status=400)

        # Validate date ranges
        if pre_end <= pre_start:
            return response.json({
                "success": False,
                "message": "Pre-campaign end date must be after start date"
            }, status=400)

        if campaign_end <= campaign_start:
            return response.json({
                "success": False,
                "message": "Campaign end date must be after start date"
            }, status=400)

        # Generate report
        etherscan_service = EtherscanService()
        report = await etherscan_service.generate_campaign_report(
            contract_address,
            pre_start,
            pre_end,
            campaign_start,
            campaign_end,
            max_pages=body.maxPages
        )

        # Store report in database if needed
        db_service = DBService(request.app.ctx.db)
        await db_service.store_campaign_report(report)

        return response.json({
            "success": True,
            "message": "Affiliate campaign report generated successfully",
            "data": report
        })

    except Exception as e:
        return response.json({
            "success": False,
            "message": f"Error generating campaign report: {str(e)}"
        }, status=500)

@etherscan_blueprint.route("/fetch-metrics", methods=["POST"])
@openapi.summary("Fetch metrics from Etherscan")
@openapi.description("Calculate token metrics from Etherscan data for a given contract address")
@openapi.body({
    "contractAddress": "0xbc7f459eE26D2F83d20Da97FCF0Eb5467B3E28a7",
    "fromDate": "2023-01-01T00:00:00Z",
    "toDate": "2023-12-31T23:59:59Z",
    "maxPages": 10,
    "sortOrder": "desc"
})
@openapi.response(200, {"success": True, "message": "Token metrics fetched successfully", "data": {}}, "Success")
@openapi.response(400, {"success": False, "message": "Invalid parameters"}, "Invalid parameters")
@openapi.response(500, {"success": False, "message": "Error fetching metrics"}, "Server error")
async def fetch_metrics(request: Request):
    """
    Fetch metrics from Etherscan for a token (Legacy endpoint)

    Note: For more comprehensive metrics, use the /campaign-report endpoint instead.
    """
    try:
        return response.json({
            "success": False,
            "message": "This endpoint is deprecated. Please use /api/etherscan/campaign-report instead for advanced metrics."
        }, status=400)
    except Exception as e:
        return response.json({
            "success": False,
            "message": f"Error fetching metrics: {e}"
        }, status=500)

