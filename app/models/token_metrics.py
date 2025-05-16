from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime


class TimeWindow(BaseModel):
    from_date: datetime = Field(..., alias="from")
    to: datetime


class MetricValue(BaseModel):
    value: Any
    unit: Optional[str] = None
    description: str


class Metrics(BaseModel):
    active_wallets: MetricValue = Field(..., alias="activeWallets")
    transaction_volume: MetricValue = Field(..., alias="transactionVolume")
    new_token_holders: MetricValue = Field(..., alias="newTokenHolders")


class TokenMetrics(BaseModel):
    campaign_id: str = Field(..., alias="campaignId")
    time_window: TimeWindow = Field(..., alias="timeWindow")
    metrics: Metrics
    last_updated: datetime = Field(..., alias="lastUpdated")

    class Config:
        allow_population_by_field_name = True

    def to_mongodb_dict(self) -> Dict:
        """Convert the model to a MongoDB-compatible dictionary"""
        return {
            "campaign_id": self.campaign_id,
            "time_window": {
                "from": self.time_window.from_date,
                "to": self.time_window.to
            },
            "metrics": {
                "active_wallets": {
                    "value": self.metrics.active_wallets.value,
                    "description": self.metrics.active_wallets.description
                },
                "transaction_volume": {
                    "value": self.metrics.transaction_volume.value,
                    "unit": self.metrics.transaction_volume.unit,
                    "description": self.metrics.transaction_volume.description
                },
                "new_token_holders": {
                    "value": self.metrics.new_token_holders.value,
                    "description": self.metrics.new_token_holders.description
                }
            },
            "last_updated": self.last_updated
        }

    @classmethod
    def from_mongodb_dict(cls, data: Dict) -> 'TokenMetrics':
        """Create a model instance from a MongoDB dictionary"""
        return cls(
            campaignId=data["campaign_id"],
            timeWindow={
                "from": data["time_window"]["from"],
                "to": data["time_window"]["to"]
            },
            metrics={
                "activeWallets": {
                    "value": data["metrics"]["active_wallets"]["value"],
                    "description": data["metrics"]["active_wallets"]["description"]
                },
                "transactionVolume": {
                    "value": data["metrics"]["transaction_volume"]["value"],
                    "unit": data["metrics"]["transaction_volume"].get("unit"),
                    "description": data["metrics"]["transaction_volume"]["description"]
                },
                "newTokenHolders": {
                    "value": data["metrics"]["new_token_holders"]["value"],
                    "description": data["metrics"]["new_token_holders"]["description"]
                }
            },
            lastUpdated=data["last_updated"]
        )
