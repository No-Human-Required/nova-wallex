<!-- source: https://developers.wallex.ir/docs/generated/get-account-card-numbers -->

# دریافت شماره کارت‌های بانکی حساب

`GET /v1/account/card-numbers`

**Base URL:** `https://api.wallex.com`

این API لیست کارت‌های بانکی کاربر را به همراه وضعیت، مالک و بانک مربوطه بازمی‌گرداند. نیازمند API Key در هدر است.

**Tags:** basic-services

## Authentication

- `ApiKeyAuth` — apiKey in header `x-api-key`

## Responses

### 200 — پاسخ موفق

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `result` | array<object> |  |  |
| `result[].id` | integer |  |  (example: `100001`) |
| `result[].card_number` | string |  |  (example: `"62198610********"`) |
| `result[].owners` | array<string> |  |  (example: `["نام صاحب حساب"]`) |
| `result[].status` | string |  |  (example: `"ACCEPTED"`) |
| `result[].is_default` | integer |  |  (example: `1`) |
| `result[].bank_details` | object |  |  |
| `result[].bank_details.code` | string |  |  (example: `"SABCIR"`) |
| `result[].bank_details.label` | string |  |  (example: `"بانک سامان"`) |
| `message` | string |  |  (example: `"The operation was successful"`) |
| `success` | boolean |  |  (example: `true`) |
| `result_info` | object |  |  |
| `result_info.page` | integer |  |  (example: `1`) |
| `result_info.per_page` | integer |  |  (example: `4`) |
| `result_info.count` | integer |  |  (example: `4`) |
| `result_info.total_count` | integer |  |  (example: `4`) |

<details><summary>Example / shape</summary>

```json
{
  "result": [
    {
      "id": 100001,
      "card_number": "62198610********",
      "owners": [
        "نام صاحب حساب"
      ],
      "status": "ACCEPTED",
      "is_default": 1,
      "bank_details": {
        "code": "SABCIR",
        "label": "بانک سامان"
      }
    }
  ],
  "message": "The operation was successful",
  "success": true,
  "result_info": {
    "page": 1,
    "per_page": 4,
    "count": 4,
    "total_count": 4
  }
}
```

</details>
