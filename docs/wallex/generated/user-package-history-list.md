<!-- source: https://developers.wallex.ir/docs/generated/user-package-history-list -->

# User Package History List

`GET /v1/prop/user/packages/history`

**Base URL:** `https://api.wallex.ir`

# GET /v1/prop/user/packages/history

This endpoint retrieves the user packages history for a user.

## Headers

This request does not require any custom header.

## Request Body Parameters

This request does not require a request body.

## Query Parameters

This request does not require any query parameters.

## Response

- `result` (array\[object\]):

    - `user_id` (number)

    - `client_id` (string)

    - `package_title` (string)

    - `dark_image_url` (string)

    - `light_image_url` (string)

    - `currency` (string)

    - `destination_currency` (string)

    - `assurance` (string)

    - `loan` (string)

    - `final_balance` (string)

    - `final_balance_without_transfers` (string)

    - `start_balance` (string)

    - `warning_limit` (string)

    - `liquidity_limit` (string)

    - `created_at` (string)

    - `finished_at` (string)

    - `expire_at` (string)

    - `close_reason` (string)

    - `status` (string)

    - `expire_days` (number)

    - `daily_fee` (string)

    - `daily_fee_discount` (string)

    - `daily_fee_after_discount` (string)

    - `final_fee` (string)

    - `final_fee_discount` (string)

    - `final_fee_after_discount` (string)

    - `open_days` (number)

    - `total_days` (number)

    - `applicable_daily_fee` (string)

    - `applicable_daily_fee_discount` (string)

    - `applicable_daily_fee_after_discount` (string)

    - `profit` (string)

    - `profit_percentage` (string)

    - `final_assurance` (string)

    - `final_payBack` (string)

- `message` (string)

- `success` (boolean)

- `result_info` (object):

    - `page` (number)

    - `per_page` (number)

    - `count` (number)

    - `total_count` (number)


## Example Response

``` json
{
  "result": [
    {
      "unique_id": 0,
      "source_client_id": "",
      "source_client_title": "",
      "destination_client_id": "",
      "destination_client_title": null,
      "source_user_type": "",
      "destination_user_type": "",
      "fa_source_user_type": "",
      "fa_destination_user_type": "",
      "currency": "",
      "value": "",
      "reason": "",
      "createdAt": ""
    }
  ],
  "message": "",
  "success": true,
  "result_info": {
    "page": 0,
    "per_page": 0,
    "count": 0,
    "total_count": 0
  }
}

 ```

**Tags:** trade-credit

## Authentication

- `x-api-key` — apiKey in header `x-api-key`

## Responses

### 200 — 200

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `message` | string |  |  (example: `"عملیات با موفقیت انجام شد"`) |
| `result` | array<object> |  |  (example: `[{"applicable_daily_fee": "2600000", "applicable_daily_fee_after_discount": "2600000", "applicable_daily_fee_discount": "0", "assurance": "20000000", "client_id": "testClientId", "close_reason": "بستن طرح", "created_at": "2025-03-12T08:49:54.000000Z", "currency": "TMN", "daily_fee": "100000", "daily_fee_after_discount": "100000", "daily_fee_discount": "0", "dark_image_url": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg", "destination_currency": "TMN", "expire_at": "2025-04-11T08:49:54.000000Z", "expire_days": 30, "final_assurance": "17400000", "final_balance": "220000000", "final_balance_without_transfers": "220000000", "final_fee": "3000000", "final_fee_after_discount": "3000000", "final_fee_discount": "0", "final_payBack": "202600000", "finished_at": "2025-04-06T11:29:08.000000Z", "light_image_url": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg", "liquidity_limit": "182600000", "loan": "200000000", "open_days": 26, "package_title": "طرح ۱۸", "profit": "-2600000", "profit_percentage": "-1.18", "start_balance": "220000000", "status": "SUSPEND", "total_days": 26, "user_id": "testUserId", "warning_limit": "252600000"}, {"applicable_daily_fee": "900000", "applicable_daily_fee_after_discount": "900000", "applicable_daily_fee_discount": "0", "assurance": "20000000", "client_id": "testClientId", "close_reason": "بستن طرح", "created_at": "2025-03-03T09:18:29.000000Z", "currency": "TMN", "daily_fee": "100000", "daily_fee_after_discount": "100000", "daily_fee_discount": "0", "dark_image_url": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg", "destination_currency": "TMN", "expire_at": "2025-04-02T09:18:29.000000Z", "expire_days": 30, "final_assurance": "19100000", "final_balance": "220000000", "final_balance_without_transfers": "220000000", "final_fee": "3000000", "final_fee_after_discount": "3000000", "final_fee_discount": "0", "final_payBack": "200900000", "finished_at": "2025-03-11T09:44:03.000000Z", "light_image_url": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg", "liquidity_limit": "180900000", "loan": "200000000", "open_days": 9, "package_title": "طرح ۱۸", "profit": "-70900000", "profit_percentage": "-24.45", "start_balance": "220000000", "status": "SUSPEND", "total_days": 9, "user_id": "testUserId", "warning_limit": "250900000"}]`) |
| `result[].applicable_daily_fee` | string |  |  (example: `"2600000"`) |
| `result[].applicable_daily_fee_after_discount` | string |  |  (example: `"2600000"`) |
| `result[].applicable_daily_fee_discount` | string |  |  (example: `"0"`) |
| `result[].assurance` | string |  |  (example: `"20000000"`) |
| `result[].client_id` | string |  |  (example: `"testClientId"`) |
| `result[].close_reason` | string |  |  (example: `"بستن طرح"`) |
| `result[].created_at` | string |  |  (example: `"2025-03-12T08:49:54.000000Z"`) |
| `result[].currency` | string |  |  (example: `"TMN"`) |
| `result[].daily_fee` | string |  |  (example: `"100000"`) |
| `result[].daily_fee_after_discount` | string |  |  (example: `"100000"`) |
| `result[].daily_fee_discount` | string |  |  (example: `"0"`) |
| `result[].dark_image_url` | string |  |  (example: `"https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg"`) |
| `result[].destination_currency` | string |  |  (example: `"TMN"`) |
| `result[].expire_at` | string |  |  (example: `"2025-04-11T08:49:54.000000Z"`) |
| `result[].expire_days` | number |  |  (example: `30`) |
| `result[].final_assurance` | string |  |  (example: `"17400000"`) |
| `result[].final_balance` | string |  |  (example: `"220000000"`) |
| `result[].final_balance_without_transfers` | string |  |  (example: `"220000000"`) |
| `result[].final_fee` | string |  |  (example: `"3000000"`) |
| `result[].final_fee_after_discount` | string |  |  (example: `"3000000"`) |
| `result[].final_fee_discount` | string |  |  (example: `"0"`) |
| `result[].final_payBack` | string |  |  (example: `"202600000"`) |
| `result[].finished_at` | string |  |  (example: `"2025-04-06T11:29:08.000000Z"`) |
| `result[].light_image_url` | string |  |  (example: `"https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg"`) |
| `result[].liquidity_limit` | string |  |  (example: `"182600000"`) |
| `result[].loan` | string |  |  (example: `"200000000"`) |
| `result[].open_days` | number |  |  (example: `26`) |
| `result[].package_title` | string |  |  (example: `"طرح ۱۸"`) |
| `result[].profit` | string |  |  (example: `"-2600000"`) |
| `result[].profit_percentage` | string |  |  (example: `"-1.18"`) |
| `result[].start_balance` | string |  |  (example: `"220000000"`) |
| `result[].status` | string |  |  (example: `"SUSPEND"`) |
| `result[].total_days` | number |  |  (example: `26`) |
| `result[].user_id` | number |  |  (example: `"testUserId"`) |
| `result[].warning_limit` | string |  |  (example: `"252600000"`) |
| `result_info` | object |  |  |
| `result_info.count` | number |  |  (example: `15`) |
| `result_info.page` | number |  |  (example: `1`) |
| `result_info.per_page` | number |  |  (example: `15`) |
| `result_info.total_count` | number |  |  (example: `15`) |
| `success` | boolean |  |  (example: `true`) |

<details><summary>Example / shape</summary>

```json
{
  "message": "عملیات با موفقیت انجام شد",
  "result": [
    {
      "applicable_daily_fee": "2600000",
      "applicable_daily_fee_after_discount": "2600000",
      "applicable_daily_fee_discount": "0",
      "assurance": "20000000",
      "client_id": "testClientId",
      "close_reason": "بستن طرح",
      "created_at": "2025-03-12T08:49:54.000000Z",
      "currency": "TMN",
      "daily_fee": "100000",
      "daily_fee_after_discount": "100000",
      "daily_fee_discount": "0",
      "dark_image_url": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
      "destination_currency": "TMN",
      "expire_at": "2025-04-11T08:49:54.000000Z",
      "expire_days": 30,
      "final_assurance": "17400000",
      "final_balance": "220000000",
      "final_balance_without_transfers": "220000000",
      "final_fee": "3000000",
      "final_fee_after_discount": "3000000",
      "final_fee_discount": "0",
      "final_payBack": "202600000",
      "finished_at": "2025-04-06T11:29:08.000000Z",
      "light_image_url": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
      "liquidity_limit": "182600000",
      "loan": "200000000",
      "open_days": 26,
      "package_title": "طرح ۱۸",
      "profit": "-2600000",
      "profit_percentage": "-1.18",
      "start_balance": "220000000",
      "status": "SUSPEND",
      "total_days": 26,
      "user_id": "testUserId",
      "warning_limit": "252600000"
    },
    {
      "applicable_daily_fee": "900000",
      "applicable_daily_fee_after_discount": "900000",
      "applicable_daily_fee_discount": "0",
      "assurance": "20000000",
      "client_id": "testClientId",
      "close_reason": "بستن طرح",
      "created_at": "2025-03-03T09:18:29.000000Z",
      "currency": "TMN",
      "daily_fee": "100000",
      "daily_fee_after_discount": "100000",
      "daily_fee_discount": "0",
      "dark_image_url": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
      "destination_currency": "TMN",
      "expire_at": "2025-04-02T09:18:29.000000Z",
      "expire_days": 30,
      "final_assurance": "19100000",
      "final_balance": "220000000",
      "final_balance_without_transfers": "220000000",
      "final_fee": "3000000",
      "final_fee_after_discount": "3000000",
      "final_fee_discount": "0",
      "final_payBack": "200900000",
      "finished_at": "2025-03-11T09:44:03.000000Z",
      "light_image_url": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
      "liquidity_limit": "180900000",
      "loan": "200000000",
      "open_days": 9,
      "package_title": "طرح ۱۸",
      "profit": "-70900000",
      "profit_percentage": "-24.45",
      "start_balance": "220000000",
      "status": "SUSPEND",
      "total_days": 9,
      "user_id": "testUserId",
      "warning_limit": "250900000"
    }
  ],
  "result_info": {
    "count": 15,
    "page": 1,
    "per_page": 15,
    "total_count": 15
  },
  "success": true
}
```

</details>
