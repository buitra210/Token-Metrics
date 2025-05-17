import aiohttp
import asyncio
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Tuple, Set
import logging
from collections import defaultdict

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import ETHERSCAN_API_KEY, ETHERSCAN_API_URL


class EtherscanService:
    def __init__(self):
        self.api_key = ETHERSCAN_API_KEY
        self.api_url = ETHERSCAN_API_URL
        self.logger = logging.getLogger(__name__)

        if not self.api_key or self.api_key == "YourEtherscanApiKeyHere":
            logging.warning("ETHERSCAN_API_KEY is not setup in config.py")
            print("WARNING: ETHERSCAN_API_KEY is not setup in config.py. Please register API key at https://etherscan.io/apis")

    #Lấy block theo timestamp
    async def get_block_by_timestamp(self, timestamp: int) -> int:
        self.logger.info(f"Getting block number for timestamp: {timestamp} ({datetime.fromtimestamp(timestamp).isoformat()})")

        params = {
            'module': 'block',
            'action': 'getblocknobytime',
            'timestamp': str(timestamp),
            'closest': 'before',  #Lấy block gần nhất trước timestamp
            'apikey': self.api_key
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.api_url, params=params) as response:
                    if response.status != 200:
                        raise Exception(f"HTTP error {response.status}: {response.reason}")

                    data = await response.json()

            if data.get('status') != '1':
                error_msg = data.get('message', 'Unknown error')
                result = data.get('result', '')
                self.logger.error(f"Etherscan API error getting block: {error_msg}, {result}")
                # Default to a recent block if error (50 blocks ago)
                return 0

            block_number = int(data.get('result', 0))
            self.logger.info(f"Block number for timestamp {timestamp}: {block_number}")
            return block_number

        except Exception as e:
            self.logger.error(f"Error getting block by timestamp: {str(e)}")
            return 0

    async def get_token_transactions_by_blocks(self, contract_address: str,
                                              from_block: int, to_block: int,
                                              max_pages: int = 10,
                                              sort_order: str = "desc",
                                              page_size: int = 1000) -> List[Dict]:
        """
        Fetch token transactions using block numbers with pagination support

        Args:
            contract_address: The token contract address
            from_block: Starting block number
            to_block: Ending block number
            max_pages: Maximum number of pages to fetch (0 for unlimited)
            sort_order: "asc" for oldest first or "desc" for newest first (default)
            page_size: Number of transactions per page (max 1000)

        Returns:
            List of transactions matching the criteria
        """
        self.logger.info(f"Fetching transactions for contract: {contract_address}")
        self.logger.info(f"Block range: {from_block} to {to_block}")
        self.logger.info(f"Sort order: {sort_order}, Max pages: {max_pages}, Page size: {page_size}")

        if sort_order not in ["asc", "desc"]:
            sort_order = "desc"

        if page_size > 1000:
            page_size = 1000

        all_transactions = []
        current_page = 1
        has_more_data = True

        #Lấy tất cả các giao dịch từ block bắt đầu đến block kết thúc
        while has_more_data and (max_pages == 0 or current_page <= max_pages):
            self.logger.info(f"Fetching page {current_page}...")

            params = {
                'module': 'account',
                'action': 'tokentx',
                'contractaddress': contract_address,
                'startblock': str(from_block),
                'endblock': str(to_block),
                'page': str(current_page),
                'offset': str(page_size),
                'sort': sort_order,
                'apikey': self.api_key
            }

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(self.api_url, params=params) as response:
                        if response.status != 200:
                            raise Exception(f"HTTP error {response.status}: {response.reason}")

                        data = await response.json()

                self.logger.info(f"Page {current_page} - Etherscan API response: Status={data.get('status')}, Message={data.get('message')}")

                if data.get('status') != '1':
                    error_msg = data.get('message', 'Unknown error')
                    result = data.get('result', '')

                    if error_msg == 'NOTOK' and 'API Key' in result:
                        raise Exception(f"Etherscan API key is invalid. Details: {result}")
                    elif 'rate limit' in str(result).lower():
                        self.logger.warning(f"Rate limit reached. Waiting before next request.")
                        await asyncio.sleep(1)  # Add delay to respect rate limits
                        continue  # Try again
                    elif 'Result window is too large' in error_msg:
                        # This is a limitation of Etherscan - can't get beyond 10k records with pagination
                        self.logger.warning(f"Reached Etherscan pagination limit (max 10,000 records). Using only first page data.")
                        has_more_data = False  # Stop trying to get more pages
                        break
                    elif contract_address in str(result):
                        raise Exception(f"Địa chỉ contract không hợp lệ hoặc không tồn tại: {result}")
                    elif 'No transactions found' in str(result):
                        self.logger.info(f"No more transactions found for this contract.")
                        has_more_data = False
                        break
                    else:
                        self.logger.warning(f"Etherscan API Error: {error_msg}. Details: {result}")
                        has_more_data = False  # Stop on unknown errors
                        break

                # If we have no transactions or empty result, end the loop
                if not data.get('result') or len(data['result']) == 0:
                    self.logger.info(f"No transactions found in page {current_page} - ending pagination")
                    has_more_data = False
                    break

                page_transactions = data['result']
                total_in_page = len(page_transactions)
                self.logger.info(f"Retrieved {total_in_page} transactions from page {current_page}")

                # Only store token info once from the first transaction
                if not hasattr(self, 'token_info') and total_in_page > 0:
                    first_tx = page_transactions[0]
                    self.token_info = {
                        'symbol': first_tx.get('tokenSymbol', 'TOKEN'),
                        'name': first_tx.get('tokenName', 'Unknown Token'),
                        'decimals': first_tx.get('tokenDecimal', '18'),
                        'divisor': 10 ** int(first_tx.get('tokenDecimal', '18'))
                    }
                    self.current_contract = contract_address

                # Append this page's results to all_transactions
                all_transactions.extend(page_transactions)

                # Check if we need to continue pagination
                if total_in_page < page_size:
                    # We got fewer results than requested, so we've reached the end
                    self.logger.info(f"Reached end of results: {total_in_page} < {page_size}")
                    has_more_data = False
                else:
                    current_page += 1
                    # Respect rate limit with a small delay between requests
                    await asyncio.sleep(0.2)

            except aiohttp.ClientError as e:
                self.logger.error(f"Lỗi kết nối đến Etherscan API: {str(e)}")
                raise Exception(f"Lỗi kết nối đến Etherscan API: {str(e)}")
            except Exception as e:
                self.logger.error(f"Lỗi khi lấy dữ liệu giao dịch ở page {current_page}: {str(e)}")
                raise Exception(f"Lỗi khi lấy dữ liệu giao dịch: {str(e)}")

        # Log stats about all transactions retrieved
        total_transactions = len(all_transactions)
        self.logger.info(f"Total transactions retrieved across all pages: {total_transactions}")

        if total_transactions > 0:
            # Log sample timestamps to verify
            self.logger.info(f"First transaction timestamp: {all_transactions[0]['timeStamp']} ({datetime.fromtimestamp(int(all_transactions[0]['timeStamp'])).isoformat()})")
            if total_transactions > 2:
                middle_idx = total_transactions // 2
                self.logger.info(f"Sample transaction timestamp: {all_transactions[middle_idx]['timeStamp']} ({datetime.fromtimestamp(int(all_transactions[middle_idx]['timeStamp'])).isoformat()})")
            self.logger.info(f"Last transaction timestamp: {all_transactions[-1]['timeStamp']} ({datetime.fromtimestamp(int(all_transactions[-1]['timeStamp'])).isoformat()})")

        return all_transactions

    async def get_token_info(self, contract_address: str) -> Dict:
        """Get basic information about a token contract using free API endpoints"""
        # Log for debugging
        self.logger.info(f"Getting token info for contract: {contract_address}")

        # Set default token info specific to this contract address
        default_info = {
            'symbol': 'TOKEN',
            'name': f"Token {contract_address[:6]}...{contract_address[-4:]}",
            'decimals': '18',
            'divisor': 10 ** 18
        }

        # Check if we already have token info from transactions
        if hasattr(self, 'token_info'):
            # Make sure the token_info is for the requested contract
            # (The bug might be here if the token_info doesn't get reset between requests)
            if getattr(self, 'current_contract', None) != contract_address:
                # If token_info is from a different contract, reset it
                if hasattr(self, 'current_contract'):
                    delattr(self, 'token_info')
            else:
                return self.token_info

        try:
            params = {
                'module': 'account',
                'action': 'tokentx',
                'contractaddress': contract_address,
                'page': '1',
                'offset': '1',  # Chỉ cần 1 giao dịch
                'sort': 'desc',  # Lấy giao dịch mới nhất
                'apikey': self.api_key
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(self.api_url, params=params) as response:
                    if response.status != 200:
                        self.logger.warning(f"HTTP error khi lấy thông tin giao dịch: {response.status}")
                        return default_info

                    data = await response.json()

            if data.get('status') == '1' and data.get('result') and len(data['result']) > 0:
                tx = data['result'][0]
                token_info = {
                    'symbol': tx.get('tokenSymbol', default_info['symbol']),
                    'name': tx.get('tokenName', default_info['name']),
                    'decimals': tx.get('tokenDecimal', default_info['decimals']),
                    'divisor': 10 ** int(tx.get('tokenDecimal', default_info['decimals']))
                }
                self.token_info = token_info
                self.current_contract = contract_address
                return token_info
            else:
                self.logger.warning(f"Không tìm thấy giao dịch nào cho token {contract_address}")
                return default_info

        except Exception as e:
            self.logger.error(f"Lỗi khi lấy thông tin token: {str(e)}")
            return default_info
# generate_campaign_report
    async def generate_wallet_action(self, contract_address: str,
                                     pre_start_time: datetime, pre_end_time: datetime,
                                     campaign_start_time: datetime, campaign_end_time: datetime,
                                     max_pages: int = 10) -> Dict:
        """
        Generate a comprehensive report for a token campaign, comparing pre and during campaign metrics

        Args:
            contract_address: Token contract address
            pre_start_time: Pre-campaign period start time
            pre_end_time: Pre-campaign period end time
            campaign_start_time: Campaign period start time
            campaign_end_time: Campaign period end time
            max_pages: Maximum number of pages to fetch per period

        Returns:
            Complete campaign report with metrics and daily data
        """
        self.logger.info(f"Generating campaign report for token: {contract_address}")
        self.logger.info(f"Pre-campaign period: {pre_start_time.isoformat()} to {pre_end_time.isoformat()}")
        self.logger.info(f"Campaign period: {campaign_start_time.isoformat()} to {campaign_end_time.isoformat()}")

        # Reset any existing token_info to prevent using data from previous requests
        if hasattr(self, 'token_info'):
            delattr(self, 'token_info')
        if hasattr(self, 'current_contract'):
            delattr(self, 'current_contract')

        # Get token info first
        token_info = await self.get_token_info(contract_address)
        token_symbol = token_info.get('symbol', 'TOKEN')

        # Convert timestamps to block numbers
        pre_start_block = await self.get_block_by_timestamp(int(pre_start_time.timestamp()))
        pre_end_block = await self.get_block_by_timestamp(int(pre_end_time.timestamp()))
        campaign_start_block = await self.get_block_by_timestamp(int(campaign_start_time.timestamp()))
        campaign_end_block = await self.get_block_by_timestamp(int(campaign_end_time.timestamp()))

        self.logger.info(f"Pre-campaign blocks: {pre_start_block} to {pre_end_block}")
        self.logger.info(f"Campaign blocks: {campaign_start_block} to {campaign_end_block}")

        pre_transactions = await self.get_token_transactions_by_blocks(
            contract_address,
            pre_start_block,
            pre_end_block,
            max_pages=max_pages,
            sort_order="desc"
        )

        campaign_transactions = await self.get_token_transactions_by_blocks(
            contract_address,
            campaign_start_block,
            campaign_end_block,
            max_pages=max_pages,
            sort_order="desc"
        )

        self.logger.info(f"Pre-campaign transactions: {len(pre_transactions)}")
        self.logger.info(f"Campaign transactions: {len(campaign_transactions)}")


        # 1. Active wallets (unique addresses participating in transactions)
        pre_wallets = set()
        for tx in pre_transactions:
            pre_wallets.add(tx['from'])
            pre_wallets.add(tx['to'])

        campaign_wallets = set()
        for tx in campaign_transactions:
            campaign_wallets.add(tx['from'])
            campaign_wallets.add(tx['to'])

        active_wallets_pre = len(pre_wallets)
        active_wallets_campaign = len(campaign_wallets)

        # Calculate change percentage
        active_wallets_change = 0
        if active_wallets_pre > 0:
            active_wallets_change = round((active_wallets_campaign - active_wallets_pre) / active_wallets_pre * 100, 1)

        # 3. New token holders
        # Find all holders before the pre-campaign period to establish baseline
        # holders_before_pre = set()

        # Get some historical transactions (if available) to establish earlier holders
        # try:
        #     historical_end_block = pre_start_block - 1
        #     historical_start_block = max(1, historical_end_block - 10000000)  # Try 10M blocks before

        #     historical_txs = await self.get_token_transactions_by_blocks(
        #         contract_address,
        #         historical_start_block,
        #         historical_end_block,
        #         max_pages=10,
        #         sort_order="asc"
        #     )

        #     for tx in historical_txs:
        #         holders_before_pre.add(tx['to'])

        #     self.logger.info(f"Historical holders found: {len(holders_before_pre)}")
        # except Exception as e:
        #     self.logger.warning(f"Unable to fetch historical holders: {str(e)}")

        # New holders during pre-campaign
        # new_holders_pre = set()
        # for tx in pre_transactions:
        #     if tx['to'] not in holders_before_pre and tx['to'] not in new_holders_pre:
        #         new_holders_pre.add(tx['to'])

        # Add pre-campaign holders to the known holders set
        # holders_before_campaign = holders_before_pre.union(new_holders_pre)

        # New holders during campaign
        # new_holders_campaign = set()
        # for tx in campaign_transactions:
        #     if tx['to'] not in holders_before_campaign and tx['to'] not in new_holders_campaign:
        #         new_holders_campaign.add(tx['to'])

        # Calculate change percentage
        # new_holders_change = 0
        # if len(new_holders_pre) > 0:
        #     new_holders_change = round((len(new_holders_campaign) - len(new_holders_pre)) / len(new_holders_pre) * 100, 1)

        # ----- Calculate daily metrics -----

        # Combine pre and campaign transactions for full timeline analysis
        all_transactions = pre_transactions + campaign_transactions

        # Sort by timestamp to ensure chronological processing
        all_transactions.sort(key=lambda tx: int(tx['timeStamp']))

        # Daily active wallets
        daily_active_wallets = defaultdict(set)

        # Daily transaction volume
        # daily_volume = defaultdict(float)

        # Daily new holders
        # daily_new_holders = defaultdict(set)

        # All known holders (including historical)
        # all_known_holders = holders_before_pre.copy()

        # Daily cumulative holders count
        daily_cumulative_holders = defaultdict(int)

        # Process transactions day by day
        for tx in all_transactions:
            # Convert timestamp to date
            tx_timestamp = int(tx['timeStamp'])
            tx_date = datetime.fromtimestamp(tx_timestamp).date().isoformat()

            # Add addresses to daily active wallets
            daily_active_wallets[tx_date].add(tx['from'])
            daily_active_wallets[tx_date].add(tx['to'])

            # Add value to daily volume
            # daily_volume[tx_date] += int(tx['value']) / token_divisor

            # Check for new holders
            # if tx['to'] not in all_known_holders:
            #     daily_new_holders[tx_date].add(tx['to'])
            #     all_known_holders.add(tx['to'])

            # Update cumulative holders for this day and all subsequent days
            # daily_cumulative_holders[tx_date] = len(all_known_holders)

        # Convert daily data to sorted list format for response
        # Format daily active wallets for the response
        daily_data = []
        all_dates = sorted(daily_active_wallets.keys())

        for date in all_dates:
            daily_entry = {
                "date": date,
                "count": len(daily_active_wallets[date])
            }
            daily_data.append(daily_entry)

        # ----- Prepare response -----

        report = {
            "campaign": {
                "token": {
                    "name": token_info.get('name', 'Unknown Token'),
                    "symbol": token_symbol,
                    "contractAddress": contract_address
                },
                "period": {
                    "preCampaign": {
                        "from": pre_start_time.isoformat(),
                        "to": pre_end_time.isoformat()
                    },
                    "duringCampaign": {
                        "from": campaign_start_time.isoformat(),
                        "to": campaign_end_time.isoformat()
                    }
                },
                "blocks": {
                    "preCampaign": {
                        "fromBlock": pre_start_block,
                        "toBlock": pre_end_block
                    },
                    "duringCampaign": {
                        "fromBlock": campaign_start_block,
                        "toBlock": campaign_end_block
                    }
                }
            },
            "summary": {
                "name": "Active Wallets",
                "preCampaign": active_wallets_pre,
                "duringCampaign": active_wallets_campaign,
                "changePercent": active_wallets_change,
                "description": "Số địa chỉ ví duy nhất đã tương tác với hợp đồng"
            },
            "dailyData": daily_data,
            "dataCollection": {
                "maxPages": max_pages,
                "transactionsAnalyzed": {
                    "preCampaign": len(pre_transactions),
                    "duringCampaign": len(campaign_transactions),
                    "total": len(pre_transactions) + len(campaign_transactions)
                }
            }
        }

        return report

    async def get_volume_transaction(self, contract_address: str, pre_start_time: datetime, pre_end_time: datetime, campaign_start_time: datetime,
                                    campaign_end_time: datetime, max_pages: int = 10) -> Dict:

        self.logger.info(f"Getting volume of transactions for token: {contract_address}")
        self.logger.info(f"Pre-campaign period: {pre_start_time.isoformat()} to {pre_end_time.isoformat()}")
        self.logger.info(f"Campaign period: {campaign_start_time.isoformat()} to {campaign_end_time.isoformat()}")

        if hasattr(self, 'token_info'):
            delattr(self, 'token_info')
        if hasattr(self, 'current_contract'):
            delattr(self, 'current_contract')

        token_info = await self.get_token_info(contract_address)
        token_symbol = token_info.get('symbol', 'TOKEN')
        token_decimals = int(token_info.get('decimals', '18'))
        token_divisor = 10 ** token_decimals

        pre_start_block = await self.get_block_by_timestamp(int(pre_start_time.timestamp()))
        pre_end_block = await self.get_block_by_timestamp(int(pre_end_time.timestamp()))
        campaign_start_block = await self.get_block_by_timestamp(int(campaign_start_time.timestamp()))
        campaign_end_block = await self.get_block_by_timestamp(int(campaign_end_time.timestamp()))

        pre_transactions = await self.get_token_transactions_by_blocks(
            contract_address,
            pre_start_block,
            pre_end_block,
            max_pages=max_pages,
            sort_order="desc"
        )

        campaign_transactions = await self.get_token_transactions_by_blocks(
            contract_address,
            campaign_start_block,
            campaign_end_block,
            max_pages=max_pages,
            sort_order="desc"
        )

        self.logger.info(f"Pre-campaign transactions: {len(pre_transactions)}")
        self.logger.info(f"Campaign transactions: {len(campaign_transactions)}")

        # Calculate volume of transactions
        pre_volume = 0
        for tx in pre_transactions:
            pre_volume += int(tx['value']) / token_divisor

        campaign_volume = 0
        for tx in campaign_transactions:
            campaign_volume += int(tx['value']) / token_divisor

        volume_change = 0
        if pre_volume > 0:
            volume_change = round((campaign_volume - pre_volume) / pre_volume * 100, 1)

        all_transactions = pre_transactions + campaign_transactions
        all_transactions.sort(key=lambda tx: int(tx['timeStamp']))

        daily_volume = defaultdict(float)
         # Process transactions day by day
        for tx in all_transactions:
            # Convert timestamp to date
            tx_timestamp = int(tx['timeStamp'])
            tx_date = datetime.fromtimestamp(tx_timestamp).date().isoformat()

            # Add value to daily volume
            daily_volume[tx_date] += int(tx['value']) / token_divisor


        daily_data = []
        all_dates = sorted(daily_volume.keys())

        for date in all_dates:
            daily_entry = {
                "date": date,
                "count": daily_volume[date]
            }
            daily_data.append(daily_entry)

        report = {
            "campaign": {
                "token": {
                    "name": token_info.get('name', 'Unknown Token'),
                    "symbol": token_symbol,
                    "contractAddress": contract_address
                },
                "period": {
                    "preCampaign": {
                        "from": pre_start_time.isoformat(),
                        "to": pre_end_time.isoformat()
                    },
                    "duringCampaign": {
                        "from": campaign_start_time.isoformat(),
                        "to": campaign_end_time.isoformat()
                    }
                },
                "blocks": {
                    "preCampaign": {
                        "fromBlock": pre_start_block,
                        "toBlock": pre_end_block
                    },
                    "duringCampaign": {
                        "fromBlock": campaign_start_block,
                        "toBlock": campaign_end_block
                    }
                }
            },
            "summary": {
                "name": "Volume Transactions",
                "preCampaign": pre_volume,
                "duringCampaign": campaign_volume,
                "changePercent": volume_change,
                "description": "Số lượng token đã chuyển đổi trong khoảng thời gian"
            },
            "dailyData": daily_data,
            "dataCollection": {
                "maxPages": max_pages,
                "transactionsAnalyzed": {
                    "preCampaign": len(pre_transactions),
                    "duringCampaign": len(campaign_transactions),
                    "total": len(pre_transactions) + len(campaign_transactions)
                }
            }
        }
        return report

    async def get_new_token_holders(self, contract_address: str, pre_start_time: datetime, pre_end_time: datetime, campaign_start_time: datetime,
                                     campaign_end_time: datetime, max_pages: int = 10) -> Dict:

        self.logger.info(f"Getting volume of transactions for token: {contract_address}")
        self.logger.info(f"Pre-campaign period: {pre_start_time.isoformat()} to {pre_end_time.isoformat()}")
        self.logger.info(f"Campaign period: {campaign_start_time.isoformat()} to {campaign_end_time.isoformat()}")

        if hasattr(self, 'token_info'):
            delattr(self, 'token_info')
        if hasattr(self, 'current_contract'):
            delattr(self, 'current_contract')

        token_info = await self.get_token_info(contract_address)
        token_symbol = token_info.get('symbol', 'TOKEN')
        token_decimals = int(token_info.get('decimals', '18'))
        token_divisor = 10 ** token_decimals

        pre_start_block = await self.get_block_by_timestamp(int(pre_start_time.timestamp()))
        pre_end_block = await self.get_block_by_timestamp(int(pre_end_time.timestamp()))
        campaign_start_block = await self.get_block_by_timestamp(int(campaign_start_time.timestamp()))
        campaign_end_block = await self.get_block_by_timestamp(int(campaign_end_time.timestamp()))

        pre_transactions = await self.get_token_transactions_by_blocks(
            contract_address,
            pre_start_block,
            pre_end_block,
            max_pages=max_pages,
            sort_order="desc"
        )

        campaign_transactions = await self.get_token_transactions_by_blocks(
            contract_address,
            campaign_start_block,
            campaign_end_block,
            max_pages=max_pages,
            sort_order="desc"
        )

        self.logger.info(f"Pre-campaign transactions: {len(pre_transactions)}")
        self.logger.info(f"Campaign transactions: {len(campaign_transactions)}")


        holders_before_pre = set()

        try:
            historical_end_block = pre_start_block - 1
            historical_start_block = max(1, historical_end_block - 10000000)

            historical_txs = await self.get_token_transactions_by_blocks(
                contract_address,
                historical_start_block,
                historical_end_block,
                max_pages=10,
                sort_order="asc"
            )

            for tx in historical_txs:
                holders_before_pre.add(tx['to'])

            self.logger.info(f"Historical holders found: {len(holders_before_pre)}")
        except Exception as e:
            self.logger.warning(f"Unable to fetch historical holders: {str(e)}")

        new_holders_pre = set()
        for tx in pre_transactions:
            if tx['to'] not in holders_before_pre and tx['to'] not in new_holders_pre:
                new_holders_pre.add(tx['to'])

        holders_before_campaign = holders_before_pre.union(new_holders_pre)

        new_holders_campaign = set()
        for tx in campaign_transactions:
            if tx['to'] not in holders_before_campaign and tx['to'] not in new_holders_campaign:
                new_holders_campaign.add(tx['to'])

        new_holders_change = 0
        if len(new_holders_pre) > 0:
            new_holders_change = round((len(new_holders_campaign) - len(new_holders_pre)) / len(new_holders_pre) * 100, 1)


        all_transactions = pre_transactions + campaign_transactions
        all_transactions.sort(key=lambda tx: int(tx['timeStamp']))

        daily_new_holders = defaultdict(set)
        daily_cumulative_holders = defaultdict(int)

        all_known_holders = holders_before_pre.copy()

        for tx in all_transactions:
            # Convert timestamp to date
            tx_timestamp = int(tx['timeStamp'])
            tx_date = datetime.fromtimestamp(tx_timestamp).date().isoformat()

            # Add value to daily volume
            if tx['to'] not in all_known_holders:
                daily_new_holders[tx_date].add(tx['to'])
                all_known_holders.add(tx['to'])
            daily_cumulative_holders[tx_date] = len(all_known_holders)


        # Generate a complete date range for both periods
        all_dates = set()

        # Generate all dates for pre-campaign period
        current_date = pre_start_time.date()
        end_date = pre_end_time.date()
        while current_date <= end_date:
            all_dates.add(current_date.isoformat())
            current_date += timedelta(days=1)

        # Generate all dates for campaign period
        current_date = campaign_start_time.date()
        end_date = campaign_end_time.date()
        while current_date <= end_date:
            all_dates.add(current_date.isoformat())
            current_date += timedelta(days=1)

        daily_data = []
        sorted_dates = sorted(all_dates)

        for date in sorted_dates:
            daily_entry = {
                "date": date,
                "count": len(daily_new_holders[date])
            }
            daily_data.append(daily_entry)

        report = {
            "campaign": {
                "token": {
                    "name": token_info.get('name', 'Unknown Token'),
                    "symbol": token_symbol,
                    "contractAddress": contract_address
                },
                "period": {
                    "preCampaign": {
                        "from": pre_start_time.isoformat(),
                        "to": pre_end_time.isoformat()
                    },
                    "duringCampaign": {
                        "from": campaign_start_time.isoformat(),
                        "to": campaign_end_time.isoformat()
                    }
                },
                "blocks": {
                    "preCampaign": {
                        "fromBlock": pre_start_block,
                        "toBlock": pre_end_block
                    },
                    "duringCampaign": {
                        "fromBlock": campaign_start_block,
                        "toBlock": campaign_end_block
                    }
                }
            },
            "summary": {
                "name": "New Token Holders",
                "preCampaign": len(new_holders_pre),
                "duringCampaign": len(new_holders_campaign),
                "changePercent": new_holders_change,
                "description": "Số địa chỉ ví mới đã nắm giữ token"
            },
            "dailyData": daily_data,
            "dataCollection": {
                "maxPages": max_pages,
                "transactionsAnalyzed": {
                    "preCampaign": len(pre_transactions),
                    "duringCampaign": len(campaign_transactions),
                    "total": len(pre_transactions) + len(campaign_transactions)
                }
            }
        }
        return report
