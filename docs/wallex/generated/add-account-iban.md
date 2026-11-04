<!-- source: https://developers.wallex.ir/docs/generated/add-account-iban -->

# افزودن شماره شبا جدید به حساب

`POST /v1/account/ibans`

**Base URL:** `https://api.wallex.com`

این API برای ثبت یک شماره شبا جدید در حساب کاربر استفاده می‌شود. نیازمند API Key در هدر است.

**Tags:** basic-services

## Authentication

- `ApiKeyAuth` — apiKey in header `x-api-key`

## Request body

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `iban` | string | yes | شماره شبا بدون پیشوند IR (example: `"230170000000230285711000"`) |

**Example:**

```json
{
  "iban": "230170000000230285711000"
}
```

## Responses

### 200 — پاسخ موفق

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `result` | object |  |  |
| `result.id` | integer |  |  (example: `4479993`) |
| `result.withdraw_daily_amount` | number |  |  (example: `10000000000`) |
| `result.withdraw_available_amount` | number |  |  (example: `10000000000`) |
| `result.iban` | string |  |  (example: `"IR560170000000230285711000"`) |
| `result.owners` | array<string> |  |  (example: `["نام صاحب حساب"]`) |
| `result.bank_name` | string |  |  (example: `"بانک ملی ایران"`) |
| `result.status` | string |  |  (example: `"PENDING"`) |
| `result.is_default` | integer |  |  (example: `0`) |
| `result.bank_details` | object |  |  |
| `result.bank_details.code` | string |  |  (example: `"MELIIR"`) |
| `result.bank_details.label` | string |  |  (example: `"بانک ملی"`) |
| `result.bank_details.is_available` | integer |  |  (example: `1`) |
| `message` | string |  |  (example: `"The operation was successful"`) |
| `success` | boolean |  |  (example: `true`) |

<details><summary>Example / shape</summary>

```json
{
  "result": {
    "id": 4479993,
    "withdraw_daily_amount": 10000000000,
    "withdraw_available_amount": 10000000000,
    "iban": "IR560170000000230285711000",
    "owners": [
      "نام صاحب حساب"
    ],
    "bank_name": "بانک ملی ایران",
    "status": "PENDING",
    "is_default": 0,
    "bank_details": {
      "code": "MELIIR",
      "label": "بانک ملی",
      "is_available": 1
    }
  },
  "message": "The operation was successful",
  "success": true
}
```

</details>
