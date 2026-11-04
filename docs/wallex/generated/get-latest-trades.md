<!-- source: https://developers.wallex.ir/docs/generated/get-latest-trades -->

# دریافت معاملات اخیر

`GET /v1/trades`

**Base URL:** `https://api.wallex.com`

این API آخرین معاملات انجام‌شده برای نماد مشخص‌شده را برمی‌گرداند.

**Tags:** basic-services

## Authentication

- `ApiKeyAuth` — apiKey in header `x-api-key`

## Parameters

| Name | In | Type | Required | Description |
| --- | --- | --- | --- | --- |
| `symbol` | query | string | yes | نماد معاملاتی مورد نظر (example: `USDCUSDT`) |

## Responses

### 200 — پاسخ موفق

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `result` | object |  |  |
| `result.latestTrades` | array<object> |  |  |
| `result.latestTrades[].symbol` | string |  |  (example: `"USDCUSDT"`) |
| `result.latestTrades[].quantity` | string |  |  (example: `"500.0000000000000000"`) |
| `result.latestTrades[].price` | string |  |  (example: `"1.0000000000000000"`) |
| `result.latestTrades[].sum` | string |  |  (example: `"500.0000000000000000"`) |
| `result.latestTrades[].isBuyOrder` | boolean |  |  (example: `false`) |
| `result.latestTrades[].timestamp` | string <date-time> |  |  (example: `"2025-06-09T13:40:05Z"`) |
| `message` | string |  |  (example: `"The operation was successful"`) |
| `success` | boolean |  |  (example: `true`) |

<details><summary>Example / shape</summary>

```json
{
  "result": {
    "latestTrades": [
      {
        "symbol": "USDCUSDT",
        "quantity": "500.0000000000000000",
        "price": "1.0000000000000000",
        "sum": "500.0000000000000000",
        "isBuyOrder": false,
        "timestamp": "2025-06-09T13:40:05Z"
      }
    ]
  },
  "message": "The operation was successful",
  "success": true
}
```

</details>
