from typing import Dict, List, Optional
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase


class DBService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.token_metrics

    async def store_metrics(self, metrics: Dict) -> str:
        """Store token metrics in MongoDB"""
        campaign_id = metrics["campaignId"]
        time_window = metrics["timeWindow"]

        # Check if a record already exists for this campaign and time window
        existing = await self.collection.find_one({
            "campaign_id": campaign_id,
            "time_window.from": time_window["from"],
            "time_window.to": time_window["to"]
        })

        if existing:
            # Update existing record
            result = await self.collection.update_one(
                {"_id": existing["_id"]},
                {"$set": {
                    "metrics": metrics["metrics"],
                    "last_updated": metrics["lastUpdated"]
                }}
            )
            return str(existing["_id"])
        else:
            # Create new record
            # Convert to snake_case for MongoDB
            db_record = {
                "campaign_id": campaign_id,
                "time_window": {
                    "from": time_window["from"],
                    "to": time_window["to"]
                },
                "metrics": {
                    "active_wallets": metrics["metrics"]["activeWallets"],
                    "transaction_volume": metrics["metrics"]["transactionVolume"],
                    "new_token_holders": metrics["metrics"]["newTokenHolders"]
                },
                "last_updated": metrics["lastUpdated"]
            }

            result = await self.collection.insert_one(db_record)
            return str(result.inserted_id)

    async def get_metrics(self, campaign_id: str, from_date: Optional[datetime] = None,
                         to_date: Optional[datetime] = None) -> List[Dict]:
        """Get metrics for a campaign with optional time filtering"""
        query = {"campaign_id": campaign_id}

        if from_date or to_date:
            query["time_window"] = {}
            if from_date:
                query["time_window"]["from"] = {"$gte": from_date.isoformat()}
            if to_date:
                query["time_window"]["to"] = {"$lte": to_date.isoformat()}

        cursor = self.collection.find(query)
        metrics = []

        async for doc in cursor:
            # Convert to camelCase for API response
            metrics.append({
                "campaignId": doc["campaign_id"],
                "timeWindow": {
                    "from": doc["time_window"]["from"],
                    "to": doc["time_window"]["to"]
                },
                "metrics": {
                    "activeWallets": doc["metrics"]["active_wallets"],
                    "transactionVolume": doc["metrics"]["transaction_volume"],
                    "newTokenHolders": doc["metrics"]["new_token_holders"]
                },
                "lastUpdated": doc["last_updated"]
            })

        return metrics
