<!-- source: https://developers.wallex.ir/docs/generated/user-package-history-details -->

# User Package History Details

`GET /v1/prop/user/packages/history/{subAccountClientId}`

**Base URL:** `https://api.wallex.ir`

# GET /v1/prop/user/packages/history/{subAccountClientId}

This endpoint retrieves the details for a historical user package.

## Headers

This request does not require any custom header.

## Request Body Parameters

This request does not require a request body.

## Query Parameters

This request does not require any query parameters.

## Response

- `result` (object):

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


## Example Response

``` json
{
    "result": {
        "user_id": testUserId,
        "client_id": "testClientId",
        "package_title": "طرح ۱۰",
        "dark_image_url": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
        "light_image_url": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
        "currency": "USDT",
        "destination_currency": "USDT",
        "assurance": "300",
        "loan": "1000",
        "final_balance": "1298.62",
        "final_balance_without_transfers": "1298.62",
        "start_balance": "1300",
        "warning_limit": "1001",
        "liquidity_limit": "1081",
        "created_at": "2025-02-08T08:47:00.000000Z",
        "finished_at": "2025-02-08T09:05:49.000000Z",
        "expire_at": "2025-03-10T08:47:00.000000Z",
        "close_reason": "بستن طرح",
        "status": "SUSPEND",
        "expire_days": 30,
        "daily_fee": "1",
        "daily_fee_discount": "0",
        "daily_fee_after_discount": "1",
        "final_fee": "30",
        "final_fee_discount": "0",
        "final_fee_after_discount": "30",
        "open_days": 1,
        "total_days": 1,
        "applicable_daily_fee": "1",
        "applicable_daily_fee_discount": "0",
        "applicable_daily_fee_after_discount": "1",
        "profit": "-2.38",
        "profit_percentage": "-0.18",
        "final_assurance": "297.62",
        "final_payBack": "1001"
    },
    "message": "عملیات با موفقیت انجام شد",
    "success": true
}

 ```

**Tags:** trade-credit

## Authentication

- `x-api-key` — apiKey in header `x-api-key`

## Parameters

| Name | In | Type | Required | Description |
| --- | --- | --- | --- | --- |
| `subAccountClientId` | path | string | yes |  |

## Responses

### 200 — 200

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `message` | string |  |  (example: `"عملیات با موفقیت انجام شد"`) |
| `result` | object |  |  |
| `result.applicable_daily_fee` | string |  |  (example: `"1"`) |
| `result.applicable_daily_fee_after_discount` | string |  |  (example: `"1"`) |
| `result.applicable_daily_fee_discount` | string |  |  (example: `"0"`) |
| `result.assurance` | string |  |  (example: `"300"`) |
| `result.client_id` | string |  |  (example: `"testClientId"`) |
| `result.close_reason` | string |  |  (example: `"بستن طرح"`) |
| `result.created_at` | string |  |  (example: `"2025-02-08T08:47:00.000000Z"`) |
| `result.currency` | string |  |  (example: `"USDT"`) |
| `result.daily_fee` | string |  |  (example: `"1"`) |
| `result.daily_fee_after_discount` | string |  |  (example: `"1"`) |
| `result.daily_fee_discount` | string |  |  (example: `"0"`) |
| `result.dark_image_url` | string |  |  (example: `"https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg"`) |
| `result.destination_currency` | string |  |  (example: `"USDT"`) |
| `result.expire_at` | string |  |  (example: `"2025-03-10T08:47:00.000000Z"`) |
| `result.expire_days` | number |  |  (example: `30`) |
| `result.final_assurance` | string |  |  (example: `"297.62"`) |
| `result.final_balance` | string |  |  (example: `"1298.62"`) |
| `result.final_balance_without_transfers` | string |  |  (example: `"1298.62"`) |
| `result.final_fee` | string |  |  (example: `"30"`) |
| `result.final_fee_after_discount` | string |  |  (example: `"30"`) |
| `result.final_fee_discount` | string |  |  (example: `"0"`) |
| `result.final_payBack` | string |  |  (example: `"1001"`) |
| `result.finished_at` | string |  |  (example: `"2025-02-08T09:05:49.000000Z"`) |
| `result.light_image_url` | string |  |  (example: `"https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg"`) |
| `result.liquidity_limit` | string |  |  (example: `"1081"`) |
| `result.loan` | string |  |  (example: `"1000"`) |
| `result.open_days` | number |  |  (example: `1`) |
| `result.package_title` | string |  |  (example: `"طرح ۱۰"`) |
| `result.profit` | string |  |  (example: `"-2.38"`) |
| `result.profit_percentage` | string |  |  (example: `"-0.18"`) |
| `result.start_balance` | string |  |  (example: `"1300"`) |
| `result.status` | string |  |  (example: `"SUSPEND"`) |
| `result.total_days` | number |  |  (example: `1`) |
| `result.user_id` | number |  |  (example: `"testUserId"`) |
| `result.warning_limit` | string |  |  (example: `"1001"`) |
| `success` | boolean |  |  (example: `true`) |

<details><summary>Example / shape</summary>

```json
{
  "message": "عملیات با موفقیت انجام شد",
  "result": {
    "applicable_daily_fee": "1",
    "applicable_daily_fee_after_discount": "1",
    "applicable_daily_fee_discount": "0",
    "assurance": "300",
    "client_id": "testClientId",
    "close_reason": "بستن طرح",
    "created_at": "2025-02-08T08:47:00.000000Z",
    "currency": "USDT",
    "daily_fee": "1",
    "daily_fee_after_discount": "1",
    "daily_fee_discount": "0",
    "dark_image_url": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
    "destination_currency": "USDT",
    "expire_at": "2025-03-10T08:47:00.000000Z",
    "expire_days": 30,
    "final_assurance": "297.62",
    "final_balance": "1298.62",
    "final_balance_without_transfers": "1298.62",
    "final_fee": "30",
    "final_fee_after_discount": "30",
    "final_fee_discount": "0",
    "final_payBack": "1001",
    "finished_at": "2025-02-08T09:05:49.000000Z",
    "light_image_url": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
    "liquidity_limit": "1081",
    "loan": "1000",
    "open_days": 1,
    "package_title": "طرح ۱۰",
    "profit": "-2.38",
    "profit_percentage": "-0.18",
    "start_balance": "1300",
    "status": "SUSPEND",
    "total_days": 1,
    "user_id": "testUserId",
    "warning_limit": "1001"
  },
  "success": true
}
```

</details>
