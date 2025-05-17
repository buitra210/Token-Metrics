response active wallet report:

"campaign": {
"token": {
"name": "My Token",
"symbol": "MTK",
"contractAddress": "0x123..."
},
"period": {
"preCampaign": {"from": "2023-04-01T00:00:00", "to": "2023-04-07T23:59:59"},
"duringCampaign": {"from": "2023-04-08T00:00:00", "to": "2023-04-14T23:59:59"}
},
"blocks": {
"preCampaign": {"fromBlock": 12340000, "toBlock": 12350000},
"duringCampaign": {"fromBlock": 12350001, "toBlock": 12360000}
}
},
"summary": {
"name": "Active Wallets",
"preCampaign": 150,
"duringCampaign": 230,
"changePercent": 53.3,
"description": "Số địa chỉ ví duy nhất đã tương tác với hợp đồng"
},
"dailyData": [
{"date": "2023-04-01", "count": 20},s
{"date": "2023-04-02", "count": 25}
],
"dataCollection": {
"maxPages": 10,
"transactionsAnalyzed": {
"preCampaign": 800,
"duringCampaign": 1200,
"total": 2000
}
}
