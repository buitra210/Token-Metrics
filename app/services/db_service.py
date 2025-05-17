from typing import Dict, List, Optional
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase


class DBService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.token_metrics
        self.campaign_reports = db.campaign_reports
        self.volume_transactions = db.volume_transactions
        self.active_wallets = db.active_wallets
        self.new_token_holders = db.new_token_holders

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

        # Handle the optional dataCollection field
        data_collection = metrics.get("dataCollection", {})

        if existing:
            # Update existing record
            update_fields = {
                "metrics": metrics["metrics"],
                "last_updated": metrics["lastUpdated"]
            }

            # Add dataCollection if present
            if data_collection:
                update_fields["data_collection"] = {
                    "max_pages": data_collection.get("maxPages", 0),
                    "sort_order": data_collection.get("sortOrder", "desc"),
                    "transactions_found": data_collection.get("transactionsFound", 0)
                }

            result = await self.collection.update_one(
                {"_id": existing["_id"]},
                {"$set": update_fields}
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

            # Add dataCollection if present
            if data_collection:
                db_record["data_collection"] = {
                    "max_pages": data_collection.get("maxPages", 0),
                    "sort_order": data_collection.get("sortOrder", "asc"),
                    "transactions_found": data_collection.get("transactionsFound", 0)
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
            metric_response = {
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
            }

            # Add dataCollection if present
            if "data_collection" in doc:
                metric_response["dataCollection"] = {
                    "maxPages": doc["data_collection"].get("max_pages", 0),
                    "sortOrder": doc["data_collection"].get("sort_order", "asc"),
                    "transactionsFound": doc["data_collection"].get("transactions_found", 0)
                }

            metrics.append(metric_response)

        return metrics

    async def store_campaign_report(self, report: Dict) -> str:

        contract_address = report.get("campaign", {}).get("token", {}).get("contractAddress")
        if not contract_address:
            raise ValueError("Report must contain a valid contract address")

        # Format periods for querying later
        pre_period = report.get("campaign", {}).get("period", {}).get("preCampaign", {})
        campaign_period = report.get("campaign", {}).get("period", {}).get("duringCampaign", {})

        # Check if report already exists for this contract and time periods
        query = {
            "contract_address": contract_address,
            "pre_period.from": pre_period.get("from"),
            "pre_period.to": pre_period.get("to"),
            "campaign_period.from": campaign_period.get("from"),
            "campaign_period.to": campaign_period.get("to")
        }

        existing = await self.campaign_reports.find_one(query)

        db_record = {
            "contract_address": contract_address,
            "pre_period": pre_period,
            "campaign_period": campaign_period,
            "report": report,
            "last_updated": datetime.now().isoformat()
        }

        if existing:
            # Update existing record
            result = await self.campaign_reports.update_one(
                {"_id": existing["_id"]},
                {"$set": db_record}
            )
            return str(existing["_id"])
        else:
            # Create new record
            result = await self.campaign_reports.insert_one(db_record)
            return str(result.inserted_id)

    async def get_campaign_report(self, contract_address: str,
                                pre_start: Optional[datetime] = None,
                                pre_end: Optional[datetime] = None,
                                campaign_start: Optional[datetime] = None,
                                campaign_end: Optional[datetime] = None) -> Optional[Dict]:

        query = {"contract_address": contract_address}

        # Add date filters if provided
        if pre_start:
            query["pre_period.from"] = {"$gte": pre_start.isoformat()}
        if pre_end:
            query["pre_period.to"] = {"$lte": pre_end.isoformat()}
        if campaign_start:
            query["campaign_period.from"] = {"$gte": campaign_start.isoformat()}
        if campaign_end:
            query["campaign_period.to"] = {"$lte": campaign_end.isoformat()}

        # Sort by last_updated to get most recent report first
        report_doc = await self.campaign_reports.find_one(
            query,
            sort=[("last_updated", -1)]
        )

        if report_doc:
            return report_doc["report"]

        return None

    async def store_active_wallets(self, report: Dict) -> str:

        contract_address = report.get("campaign", {}).get("token", {}).get("contractAddress")
        if not contract_address:
            raise ValueError("Report must contain a valid contract address")

        # Format periods for querying later
        pre_period = report.get("campaign", {}).get("period", {}).get("preCampaign", {})
        campaign_period = report.get("campaign", {}).get("period", {}).get("duringCampaign", {})

        # Check if report already exists for this contract and time periods
        query = {
            "contract_address": contract_address,
            "pre_period.from": pre_period.get("from"),
            "pre_period.to": pre_period.get("to"),
            "campaign_period.from": campaign_period.get("from"),
            "campaign_period.to": campaign_period.get("to")
        }

        existing = await self.active_wallets.find_one(query)

        db_record = {
            "contract_address": contract_address,
            "pre_period": pre_period,
            "campaign_period": campaign_period,
            "report": report,
            "last_updated": datetime.now().isoformat()
        }

        if existing:
            # Update existing record
            result = await self.active_wallets.update_one(
                {"_id": existing["_id"]},
                {"$set": db_record}
            )
            return str(existing["_id"])
        else:
            # Create new record
            result = await self.active_wallets.insert_one(db_record)
            return str(result.inserted_id)

    async def get_active_wallets(self, contract_address: str,
                                pre_start: Optional[datetime] = None,
                                pre_end: Optional[datetime] = None,
                                campaign_start: Optional[datetime] = None,
                                campaign_end: Optional[datetime] = None) -> Optional[Dict]:
        """
        Retrieve campaign report from MongoDB with optional time filtering

        Args:
            contract_address: Token contract address
            pre_start: Pre-campaign start time for filtering
            pre_end: Pre-campaign end time for filtering
            campaign_start: Campaign start time for filtering
            campaign_end: Campaign end time for filtering

        Returns:
            Campaign report if found, None otherwise
        """
        query = {"contract_address": contract_address}

        # Add date filters if provided
        if pre_start:
            query["pre_period.from"] = {"$gte": pre_start.isoformat()}
        if pre_end:
            query["pre_period.to"] = {"$lte": pre_end.isoformat()}
        if campaign_start:
            query["campaign_period.from"] = {"$gte": campaign_start.isoformat()}
        if campaign_end:
            query["campaign_period.to"] = {"$lte": campaign_end.isoformat()}

        # Sort by last_updated to get most recent report first
        report_doc = await self.active_wallets.find_one(
            query,
            sort=[("last_updated", -1)]
        )

        if report_doc:
            return report_doc["report"]

        return None

    async def store_volume_transactions(self, report: Dict) -> str:
        """
        Store campaign report in MongoDB

        Args:
            report: Complete campaign report generated by EtherscanService

        Returns:
            ID of the stored report
        """
        contract_address = report.get("campaign", {}).get("token", {}).get("contractAddress")
        if not contract_address:
            raise ValueError("Report must contain a valid contract address")

        # Format periods for querying later
        pre_period = report.get("campaign", {}).get("period", {}).get("preCampaign", {})
        campaign_period = report.get("campaign", {}).get("period", {}).get("duringCampaign", {})

        # Check if report already exists for this contract and time periods
        query = {
            "contract_address": contract_address,
            "pre_period.from": pre_period.get("from"),
            "pre_period.to": pre_period.get("to"),
            "campaign_period.from": campaign_period.get("from"),
            "campaign_period.to": campaign_period.get("to")
        }

        existing = await self.volume_transactions.find_one(query)

        db_record = {
            "contract_address": contract_address,
            "pre_period": pre_period,
            "campaign_period": campaign_period,
            "report": report,
            "last_updated": datetime.now().isoformat()
        }

        if existing:
            # Update existing record
            result = await self.volume_transactions.update_one(
                {"_id": existing["_id"]},
                {"$set": db_record}
            )
            return str(existing["_id"])
        else:
            # Create new record
            result = await self.volume_transactions.insert_one(db_record)
            return str(result.inserted_id)

    async def get_volume_transactions(self, contract_address: str,
                                pre_start: Optional[datetime] = None,
                                pre_end: Optional[datetime] = None,
                                campaign_start: Optional[datetime] = None,
                                campaign_end: Optional[datetime] = None) -> Optional[Dict]:
        query = {"contract_address": contract_address}

        # Add date filters if provided
        if pre_start:
            query["pre_period.from"] = {"$gte": pre_start.isoformat()}
        if pre_end:
            query["pre_period.to"] = {"$lte": pre_end.isoformat()}
        if campaign_start:
            query["campaign_period.from"] = {"$gte": campaign_start.isoformat()}
        if campaign_end:
            query["campaign_period.to"] = {"$lte": campaign_end.isoformat()}

        # Sort by last_updated to get most recent report first
        report_doc = await self.volume_transactions.find_one(
            query,
            sort=[("last_updated", -1)]
        )

        if report_doc:
            return report_doc["report"]

        return None

    async def store_new_token_holders(self, report: Dict) -> str:
        """
        Store campaign report in MongoDB

        Args:
            report: Complete campaign report generated by EtherscanService

        Returns:
            ID of the stored report
        """
        contract_address = report.get("campaign", {}).get("token", {}).get("contractAddress")
        if not contract_address:
            raise ValueError("Report must contain a valid contract address")

        # Format periods for querying later
        pre_period = report.get("campaign", {}).get("period", {}).get("preCampaign", {})
        campaign_period = report.get("campaign", {}).get("period", {}).get("duringCampaign", {})

        # Check if report already exists for this contract and time periods
        query = {
            "contract_address": contract_address,
            "pre_period.from": pre_period.get("from"),
            "pre_period.to": pre_period.get("to"),
            "campaign_period.from": campaign_period.get("from"),
            "campaign_period.to": campaign_period.get("to")
        }

        existing = await self.new_token_holders.find_one(query)

        db_record = {
            "contract_address": contract_address,
            "pre_period": pre_period,
            "campaign_period": campaign_period,
            "report": report,
            "last_updated": datetime.now().isoformat()
        }

        if existing:
            # Update existing record
            result = await self.new_token_holders.update_one(
                {"_id": existing["_id"]},
                {"$set": db_record}
            )
            return str(existing["_id"])
        else:
            # Create new record
            result = await self.new_token_holders.insert_one(db_record)
            return str(result.inserted_id)

    async def get_new_token_holders(self, contract_address: str,
                                pre_start: Optional[datetime] = None,
                                pre_end: Optional[datetime] = None,
                                campaign_start: Optional[datetime] = None,
                                campaign_end: Optional[datetime] = None) -> Optional[Dict]:
        query = {"contract_address": contract_address}

        # Add date filters if provided
        if pre_start:
            query["pre_period.from"] = {"$gte": pre_start.isoformat()}
        if pre_end:
            query["pre_period.to"] = {"$lte": pre_end.isoformat()}
        if campaign_start:
            query["campaign_period.from"] = {"$gte": campaign_start.isoformat()}
        if campaign_end:
            query["campaign_period.to"] = {"$lte": campaign_end.isoformat()}

        # Sort by last_updated to get most recent report first
        report_doc = await self.new_token_holders.find_one(
            query,
            sort=[("last_updated", -1)]
        )

        if report_doc:
            return report_doc["report"]

        return None



