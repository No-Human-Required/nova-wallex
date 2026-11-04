<!-- source: https://developers.wallex.ir/docs/generated/get-account-ibans -->

# دریافت لیست شماره شباهای حساب

`GET /v1/account/ibans`

**Base URL:** `https://api.wallex.com`

این API لیست شماره شباهای بانکی کاربر را به همراه وضعیت، مالک و بانک مربوطه بازمی‌گرداند. نیازمند API Key در هدر است.

**Tags:** basic-services

## Authentication

- `ApiKeyAuth` — apiKey in header `x-api-key`

## Parameters

| Name | In | Type | Required | Description |
| --- | --- | --- | --- | --- |
| `per_page` | query | integer |  | تعداد آیتم‌ها در هر صفحه (example: `10`) |
| `page` | query | integer |  | شماره صفحه مورد نظر (example: `1`) |

## Responses

### 200 — پاسخ موفق

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `result` | array<object> |  |  |
| `result[].id` | integer |  |  (example: `4479113`) |
| `result[].withdraw_daily_amount` | number |  |  (example: `100000000`) |
| `result[].withdraw_available_amount` | number |  |  (example: `100000000`) |
| `result[].iban` | string |  |  (example: `"IR2301700000002302857*****"`) |
| `result[].owners` | array<string> |  |  (example: `["صاحب حساب"]`) |
| `result[].bank_name` | string |  |  (example: `"MELLI"`) |
| `result[].status` | string |  |  (example: `"ACCEPTED"`) |
| `result[].is_default` | integer |  |  (example: `0`) |
| `result[].bank_details` | object |  |  |
| `result[].bank_details.code` | string |  |  (example: `"MELIIR"`) |
| `result[].bank_details.label` | string |  |  (example: `"بانک ملی"`) |
| `result[].bank_details.is_available` | integer |  |  (example: `1`) |
| `message` | string |  |  (example: `"The operation was successful"`) |
| `success` | boolean |  |  (example: `true`) |
| `result_info` | object |  |  |
| `result_info.page` | integer |  |  (example: `1`) |
| `result_info.per_page` | integer |  |  (example: `5`) |
| `result_info.count` | integer |  |  (example: `5`) |
| `result_info.total_count` | integer |  |  (example: `5`) |

<details><summary>Example / shape</summary>

```json
{
  "result": [
    {
      "id": 4479113,
      "withdraw_daily_amount": 100000000,
      "withdraw_available_amount": 100000000,
      "iban": "IR2301700000002302857*****",
      "owners": [
        "صاحب حساب"
      ],
      "bank_name": "MELLI",
      "status": "ACCEPTED",
      "is_default": 0,
      "bank_details": {
        "code": "MELIIR",
        "label": "بانک ملی",
        "is_available": 1
      }
    }
  ],
  "message": "The operation was successful",
  "success": true,
  "result_info": {
    "page": 1,
    "per_page": 5,
    "count": 5,
    "total_count": 5
  }
}
```

</details>
