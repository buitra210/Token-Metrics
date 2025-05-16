import aiohttp
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import ETHERSCAN_API_KEY, ETHERSCAN_API_URL


class EtherscanService:
    def __init__(self):
        self.api_key = ETHERSCAN_API_KEY
        self.api_url = ETHERSCAN_API_URL

        # Kiểm tra API key
        if not self.api_key or self.api_key == "YourEtherscanApiKeyHere":
            logging.warning("ETHERSCAN_API_KEY không được cấu hình hoặc không hợp lệ")
            print("CẢNH BÁO: ETHERSCAN_API_KEY không được cấu hình. Đăng ký API key tại https://etherscan.io/apis")

    async def get_token_transactions(self, contract_address: str, start_time: Optional[datetime] = None,
                                    end_time: Optional[datetime] = None) -> List[Dict]:
        """Get all transactions for a specific token contract"""
        if not start_time:
            start_time = datetime.now() - timedelta(days=30)
        if not end_time:
            end_time = datetime.now()

        # Convert datetime to timestamp
        start_timestamp = int(start_time.timestamp())
        end_timestamp = int(end_time.timestamp())

        # Etherscan API has a 'tokentx' action to get token transfers
        params = {
            'module': 'account',
            'action': 'tokentx',
            'contractaddress': contract_address,
            'startblock': '0',
            'endblock': '999999999',
            'sort': 'asc',
            'apikey': self.api_key
        }

        try:
            # Make API request to Etherscan
            async with aiohttp.ClientSession() as session:
                async with session.get(self.api_url, params=params) as response:
                    # Kiểm tra status code
                    if response.status != 200:
                        raise Exception(f"HTTP error {response.status}: {response.reason}")

                    data = await response.json()

            # Debug response
            print(f"Etherscan API response for transactions: Status={data.get('status')}, Message={data.get('message')}")

            if data.get('status') != '1':
                error_msg = data.get('message', 'Unknown error')
                result = data.get('result', '')

                if error_msg == 'NOTOK' and 'API Key' in result:
                    raise Exception(f"Etherscan API key không hợp lệ hoặc rate limit bị vượt quá. Chi tiết: {result}")
                elif 'rate limit' in result.lower():
                    raise Exception(f"Etherscan API rate limit bị vượt quá. Vui lòng thử lại sau: {result}")
                elif contract_address in result:
                    raise Exception(f"Địa chỉ contract không hợp lệ hoặc không tồn tại: {result}")
                else:
                    raise Exception(f"Etherscan API Error: {error_msg}. Details: {result}")

            # Lấy thông tin token từ giao dịch đầu tiên (nếu có)
            # Thông tin này là miễn phí, không cần API Pro
            if data.get('result') and len(data['result']) > 0:
                first_tx = data['result'][0]
                token_info = {
                    'symbol': first_tx.get('tokenSymbol', 'TOKEN'),
                    'name': first_tx.get('tokenName', 'Unknown Token'),
                    'decimals': first_tx.get('tokenDecimal', '18'),
                    'divisor': 10 ** int(first_tx.get('tokenDecimal', '18'))
                }
                # Lưu thông tin token vào class để tái sử dụng
                self.token_info = token_info

            # Filter transactions by time
            transactions = []
            for tx in data['result']:
                tx_timestamp = int(tx['timeStamp'])
                if start_timestamp <= tx_timestamp <= end_timestamp:
                    transactions.append(tx)

            return transactions
        except aiohttp.ClientError as e:
            raise Exception(f"Lỗi kết nối đến Etherscan API: {str(e)}")
        except Exception as e:
            raise Exception(f"Lỗi khi lấy dữ liệu giao dịch: {str(e)}")

    async def get_token_info(self, contract_address: str) -> Dict:
        """Get basic information about a token contract using free API endpoints"""
        # Kiểm tra xem đã có thông tin token từ giao dịch chưa
        if hasattr(self, 'token_info'):
            return self.token_info

        # Sử dụng thông tin mặc định (ERC20 tiêu chuẩn)
        default_info = {
            'symbol': 'TOKEN',
            'name': 'Unknown Token',
            'decimals': '18',
            'divisor': 10 ** 18
        }

        try:
            # Thử phương pháp 1: Lấy thông tin từ giao dịch gần đây nhất
            # Không cần API Pro, sử dụng miễn phí
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
                        print(f"HTTP error khi lấy thông tin giao dịch: {response.status}")
                        return default_info

                    data = await response.json()

            if data.get('status') == '1' and data.get('result') and len(data['result']) > 0:
                tx = data['result'][0]
                return {
                    'symbol': tx.get('tokenSymbol', default_info['symbol']),
                    'name': tx.get('tokenName', default_info['name']),
                    'decimals': tx.get('tokenDecimal', default_info['decimals']),
                    'divisor': 10 ** int(tx.get('tokenDecimal', default_info['decimals']))
                }
            else:
                print(f"Không tìm thấy giao dịch nào cho token {contract_address}")
                return default_info

        except Exception as e:
            print(f"Lỗi khi lấy thông tin token: {str(e)}")
            return default_info

    async def calculate_metrics(self, contract_address: str, start_time: datetime, end_time: datetime) -> Dict:
        """Calculate metrics for a token in the given time window"""
        try:
            transactions = await self.get_token_transactions(contract_address, start_time, end_time)
            token_info = await self.get_token_info(contract_address)

            token_symbol = token_info.get('symbol', 'TOKEN')
            token_decimals = int(token_info.get('decimals', '18'))
            token_divisor = 10 ** token_decimals

            # Calculate active wallets (unique addresses that interacted with the contract)
            unique_addresses = set()
            for tx in transactions:
                unique_addresses.add(tx['from'])
                unique_addresses.add(tx['to'])
            active_wallets = len(unique_addresses)

            # Calculate transaction volume
            transaction_volume = 0
            for tx in transactions:
                value = int(tx['value']) / token_divisor
                transaction_volume += value

            # Calculate new token holders (addresses that received tokens for the first time)
            holders_before = set()
            new_holders = set()

            # Get transactions before the start time to determine existing holders
            try:
                earlier_txs = await self.get_token_transactions(contract_address,
                                                          start_time - timedelta(days=365),
                                                          start_time - timedelta(seconds=1))
                for tx in earlier_txs:
                    holders_before.add(tx['to'])
            except Exception as e:
                print(f"Cảnh báo khi lấy dữ liệu trước đó: {str(e)}")
                # Tiếp tục mặc dù có lỗi

            # Find new holders during the campaign period
            for tx in transactions:
                if tx['to'] not in holders_before and tx['to'] not in new_holders:
                    new_holders.add(tx['to'])

            # Create the metrics response
            return {
                "campaignId": contract_address,
                "timeWindow": {
                    "from": start_time.isoformat(),
                    "to": end_time.isoformat()
                },
                "metrics": {
                    "activeWallets": {
                        "value": active_wallets,
                        "description": "Số địa chỉ ví đã tham gia giao dịch với campaign"
                    },
                    "transactionVolume": {
                        "value": str(transaction_volume),
                        "unit": token_symbol,
                        "description": "Tổng lượng token đã chuyển qua contract"
                    },
                    "newTokenHolders": {
                        "value": len(new_holders),
                        "description": "Số địa chỉ ví mới lần đầu nắm giữ token sau campaign"
                    }
                },
                "lastUpdated": datetime.now().isoformat()
            }
        except Exception as e:
            raise Exception(f"Lỗi khi tính metrics: {str(e)}")
