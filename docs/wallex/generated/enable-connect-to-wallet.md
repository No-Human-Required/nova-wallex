<!-- source: https://developers.wallex.ir/docs/generated/enable-connect-to-wallet -->

# Enable Connect To Wallet

`POST /v1/prop/user/packages/connect-to-wallet`

**Base URL:** `https://api.wallex.ir`

# POST /v1/prop/user/packages/connect-to-wallet

This endpoint enables connect to wallet for a user package based on sub account.

## Headers

- `Sub-Account-Client-id` (string)

## Request Body Parameters

- `credit` (string)
- `usageCount` (number)
- `currency` (string)

## Query Parameters

This request does not require any query parameters.

## Response

- `result` (object)

    - `currency` (string)

    - `credit` (string)

    - `usageCount` (number)

    - `usedCount` (number)

    - `status` (string)

- `message` (string)
- `success` (boolean)

## Example Response

``` json
{
    "result": {
        "currency": "USDT",
        "credit": "10000",
        "usageCount": 3,
        "usedCount": 0,
        "status": "active"
    },
    "message": "اتصال کیف پول با موفقیت انجام شد",
    "success": true
}

 ```

**Tags:** trade-credit

## Authentication

- `x-api-key` — apiKey in header `x-api-key`

## Parameters

| Name | In | Type | Required | Description |
| --- | --- | --- | --- | --- |
| `sub-account-client-id` | header | string |  |  |

## Request body

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `credit` | string |  |  (example: `"10000"`) |
| `currency` | string |  |  (example: `"USDT"`) |
| `usageCount` | number |  |  (example: `3`) |

**Example:**

```json
{
  "credit": "10000",
  "currency": "USDT",
  "usageCount": 3
}
```

## Responses

### 200 — 200

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `message` | string |  |  (example: `"اتصال کیف پول با موفقیت انجام شد"`) |
| `result` | object |  |  |
| `result.credit` | string |  |  (example: `"10000"`) |
| `result.currency` | string |  |  (example: `"USDT"`) |
| `result.status` | string |  |  (example: `"active"`) |
| `result.usageCount` | number |  |  (example: `3`) |
| `result.usedCount` | number |  |  (example: `0`) |
| `success` | boolean |  |  (example: `true`) |

<details><summary>Example / shape</summary>

```json
{
  "message": "اتصال کیف پول با موفقیت انجام شد",
  "result": {
    "credit": "10000",
    "currency": "USDT",
    "status": "active",
    "usageCount": 3,
    "usedCount": 0
  },
  "success": true
}
```

</details>
