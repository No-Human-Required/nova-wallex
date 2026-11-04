<!-- source: https://developers.wallex.ir/docs/generated/get-account-fees -->

# دریافت کارمزدهای حساب

`GET /v1/account/fee`

**Base URL:** `https://api.wallex.com`

این API نرخ‌های کارمزد میکر و تیکر را برای هر بازار به همراه مجموع حجم معاملات چند روز اخیر باز می‌گرداند. نیازمند API Key در هدر است.

**Tags:** basic-services

## Authentication

- `ApiKeyAuth` — apiKey in header `x-api-key`

## Responses

### 200 — پاسخ موفق

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `success` | boolean |  |  (example: `true`) |
| `message` | string |  |  (example: `"عملیات با موفقیت انجام شد"`) |
| `result` | object |  |  |
| `result.{key}.makerFeeRate` | string |  |  (example: `"0.00200000"`) |
| `result.{key}.takerFeeRate` | string |  |  (example: `"0.00200000"`) |
| `result.{key}.recent_days_sum` | number <double> |  |  (example: `250000000`) |

<details><summary>Example / shape</summary>

```json
{
  "success": true,
  "message": "عملیات با موفقیت انجام شد",
  "result": {
    "<key>": {
      "makerFeeRate": "0.00200000",
      "takerFeeRate": "0.00200000",
      "recent_days_sum": 250000000
    }
  }
}
```

</details>
