<!-- source: https://developers.wallex.ir/docs/generated/get-market-depth -->

# دریافت عمق بازار

`GET /v1/depth`

**Base URL:** `https://api.wallex.com`

این API، لیست سفارشات خرید (bid) و فروش (ask) را برای یک نماد خاص برمی‌گرداند.

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
| `result.ask` | array<object> |  |  |
| `result.ask[].price` | number |  |  (example: `1.0045`) |
| `result.ask[].quantity` | number |  |  (example: `314.37`) |
| `result.ask[].sum` | string |  |  (example: `"315.784665"`) |
| `result.bid` | array<object> |  |  |
| `result.bid[].price` | number |  |  (example: `1.0045`) |
| `result.bid[].quantity` | number |  |  (example: `314.37`) |
| `result.bid[].sum` | string |  |  (example: `"315.784665"`) |
| `message` | string |  |  (example: `"عملیات موفقیت‌آمیز بود."`) |
| `success` | boolean |  |  (example: `true`) |

<details><summary>Example / shape</summary>

```json
{
  "result": {
    "ask": [
      {
        "price": 1.0045,
        "quantity": 314.37,
        "sum": "315.784665"
      }
    ],
    "bid": [
      {
        "price": 1.0045,
        "quantity": 314.37,
        "sum": "315.784665"
      }
    ]
  },
  "message": "عملیات موفقیت‌آمیز بود.",
  "success": true
}
```

</details>
