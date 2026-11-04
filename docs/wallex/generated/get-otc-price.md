<!-- source: https://developers.wallex.ir/docs/generated/get-otc-price -->

# get otc price

`GET /v1/account/otc/price`

**Base URL:** `https://api.wallex.ir`

retrieves otc prices

**Tags:** otc

## Authentication

- `ApiKeyAuth` — apiKey in header `x-api-key`

## Parameters

| Name | In | Type | Required | Description |
| --- | --- | --- | --- | --- |
| `symbol` | query | string | yes | نماد معاملاتی مورد نظر برای دریافت قیمت OTC (example: `BTCTMN`) |
| `side` | query | string (BUY | SELL) | yes | نوع عملیات؛ خرید یا فروش (example: `BUY`) |

## Responses

### 200 — پاسخ موفق

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `success` | boolean |  |  (example: `true`) |
| `message` | string |  |  (example: `"عملیات با موفقیت انجام شد"`) |
| `result` | object |  |  |
| `result.price` | string |  |  (example: `"10060906814.238"`) |
| `result.price_expires_at` | string <date-time> |  |  (example: `"2025-07-12T14:37:12Z"`) |
| `result.ttl` | integer |  | زمان اعتبار قیمت بر حسب ثانیه (example: `17`) |
| `result.current_time` | string <date-time> |  |  (example: `"2025-07-12T14:36:55Z"`) |

<details><summary>Example / shape</summary>

```json
{
  "success": true,
  "message": "عملیات با موفقیت انجام شد",
  "result": {
    "price": "10060906814.238",
    "price_expires_at": "2025-07-12T14:37:12Z",
    "ttl": 17,
    "current_time": "2025-07-12T14:36:55Z"
  }
}
```

</details>
