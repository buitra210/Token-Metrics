from sanic import Blueprint, response
from sanic.request import Request
from datetime import datetime
from app.services.db_service import DBService
from typing import Optional, Dict, Any
from pydantic import BaseModel
from sanic_ext import openapi

# Define response models
class TokenResponse(BaseModel):
    name: str
    symbol: str
    contractAddress: str

class PeriodResponse(BaseModel):
    preCampaign: Dict[str, str]
    duringCampaign: Dict[str, str]

class BlocksResponse(BaseModel):
    preCampaign: Dict[str, int]
    duringCampaign: Dict[str, int]

class CampaignResponse(BaseModel):
    token: TokenResponse
    period: PeriodResponse
    blocks: BlocksResponse

class SummaryResponse(BaseModel):
    name: str
    preCampaign: int
    duringCampaign: int
    changePercent: float
    description: str

class DailyDataItem(BaseModel):
    date: str
    count: int

class TransactionsAnalyzed(BaseModel):
    preCampaign: int
    duringCampaign: int
    total: int

class DataCollectionResponse(BaseModel):
    maxPages: int
    transactionsAnalyzed: TransactionsAnalyzed

class TokenMetricsResponse(BaseModel):
    campaign: CampaignResponse
    summary: SummaryResponse
    dailyData: list[DailyDataItem]
    dataCollection: DataCollectionResponse

token_metrics_blueprint = Blueprint('token_metrics', url_prefix='/api/metrics')

@token_metrics_blueprint.route("/<campaign_id:str>", methods=["GET"])
@openapi.summary("Get metrics for a campaign")
@openapi.description("Get all metrics for a specific campaign/token address, with optional date filtering")
@openapi.parameter("campaign_id", str, "Campaign ID (Ethereum contract address)", required=True)
@openapi.parameter("from_date", str, "Start date (ISO format, e.g. 2023-01-01T00:00:00Z)", required=False)
@openapi.parameter("to_date", str, "End date (ISO format, e.g. 2023-12-31T23:59:59Z)", required=False)
@openapi.response(200, {"success": True, "data": {}}, "Successful response")
@openapi.response(400, {"success": False, "message": "string"}, "Invalid parameters")
@openapi.response(404, {"success": False, "message": "string"}, "No metrics found")
@openapi.response(500, {"success": False, "message": "string"}, "Server error")
async def get_campaign_metrics(request: Request, campaign_id: str):
    """
    Get metrics for a specific campaign
    """
    try:
        # Check if address is valid Ethereum address
        if not campaign_id.startswith('0x') or len(campaign_id) != 42:
            return response.json({
                "success": False,
                "message": f"Invalid Ethereum address format: {campaign_id}. Address must be in format 0x... and 42 characters long."
            }, status=400)

        # Parse date parameters if provided
        from_date = request.args.get('from_date')
        to_date = request.args.get('to_date')

        if from_date:
            try:
                from_date = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
            except ValueError:
                return response.json({
                    "success": False,
                    "message": f"Invalid from_date format. Use ISO format (e.g. 2023-01-01T00:00:00Z)"
                }, status=400)

        if to_date:
            try:
                to_date = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
            except ValueError:
                return response.json({
                    "success": False,
                    "message": f"Invalid to_date format. Use ISO format (e.g. 2023-01-01T00:00:00Z)"
                }, status=400)

        # Get metrics from database
        db_service = DBService(request.app.ctx.db)
        metrics = await db_service.get_campaign_report(campaign_id, from_date, to_date)

        if not metrics:
            return response.json({
                "success": False,
                "message": f"No metrics found for campaign {campaign_id}. Try fetching metrics first via /api/etherscan/campaign-report"
            }, status=404)

        return response.json({
            "success": True,
            "data": metrics
        })

    except Exception as e:
        return response.json({
            "success": False,
            "message": f"Error retrieving metrics: {str(e)}"
        }, status=500)
