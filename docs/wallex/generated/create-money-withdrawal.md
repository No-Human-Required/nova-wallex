<!-- source: https://developers.wallex.ir/docs/generated/create-money-withdrawal -->

# درخواست برداشت وجه از حساب

`POST /v1/account/money-withdrawal`

**Base URL:** `https://api.wallex.com`

این API برای ثبت درخواست برداشت وجه از حساب کاربر استفاده می‌شود. نیازمند API Key در هدر است.

**Tags:** basic-services

## Authentication

- `ApiKeyAuth` — apiKey in header `x-api-key`

## Request body

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `iban` | integer | yes | شناسه IBAN مورد نظر برای برداشت (example: `3799240`) |
| `value` | number | yes | مقدار برداشت (به ریال) (example: `20000`) |

**Example:**

```json
{
  "iban": 3799240,
  "value": 20000
}
```

## Responses

### 201 — درخواست برداشت با موفقیت ثبت شد

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `result` | object |  |  |
| `result.amount` | number |  |  (example: `20000`) |
| `result.fee` | number |  |  (example: `200`) |
| `result.tracking_code` | string |  |  (example: `"abc123x"`) |
| `result.created_at` | string <date-time> |  |  (example: `"2025-10-27T07:24:21Z"`) |
| `result.status` | string |  |  (example: `"pending"`) |
| `result.iban` | object |  |  |
| `result.iban.id` | integer |  |  (example: `3799240`) |
| `result.iban.iban` | string |  |  (example: `"IR560560611828005*****8401"`) |
| `result.iban.owners` | array<string> |  |  (example: `["نام صاحب حساب"]`) |
| `result.iban.bank_name` | string |  |  (example: `"SAMAN"`) |
| `result.iban.status` | string |  |  (example: `"ACCEPTED"`) |
| `result.iban.is_default` | integer |  |  (example: `0`) |
| `result.iban.bank_details` | object |  |  |
| `result.iban.bank_details.code` | string |  |  (example: `"SABCIR"`) |
| `result.iban.bank_details.label` | string |  |  (example: `"بانک سامان"`) |
| `result.iban.bank_details.is_available` | integer |  |  (example: `1`) |
| `result.details` | array<object> |  |  |
| `result.details[].value` | number |  |  (example: `19800`) |
| `result.details[].status` | string |  |  (example: `"pending"`) |
| `message` | string |  |  (example: `"درخواست برداشت ثبت شد"`) |
| `success` | boolean |  |  (example: `true`) |

<details><summary>Example / shape</summary>

```json
{
  "result": {
    "amount": 20000,
    "fee": 200,
    "tracking_code": "abc123x",
    "created_at": "2025-10-27T07:24:21Z",
    "status": "pending",
    "iban": {
      "id": 3799240,
      "iban": "IR560560611828005*****8401",
      "owners": [
        "نام صاحب حساب"
      ],
      "bank_name": "SAMAN",
      "status": "ACCEPTED",
      "is_default": 0,
      "bank_details": {
        "code": "SABCIR",
        "label": "بانک سامان",
        "is_available": 1
      }
    },
    "details": [
      {
        "value": 19800,
        "status": "pending"
      }
    ]
  },
  "message": "درخواست برداشت ثبت شد",
  "success": true
}
```

</details>
