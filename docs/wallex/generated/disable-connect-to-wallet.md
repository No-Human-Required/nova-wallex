<!-- source: https://developers.wallex.ir/docs/generated/disable-connect-to-wallet -->

# Disable Connect To Wallet

`DELETE /v1/prop/user/packages/connect-to-wallet`

**Base URL:** `https://api.wallex.ir`

# DELETE /v1/prop/user/packages/connect-to-wallet

This endpoint disables connect to wallet for a user package based on sub account.

## Headers

- `Sub-Account-Client-id` (string)

## Request Body Parameters

This request does not require a request body.

## Query Parameters

This request does not require any query parameters.

## Response

- `result` (array)
- `message` (string)
- `success` (boolean)

## Example Response

``` json
{
    "result": [],
    "message": "قطع اتصال کیف پول با موفقیت انجام شد",
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

## Responses

### 200 — 200

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `message` | string |  |  (example: `"قطع اتصال کیف پول با موفقیت انجام شد"`) |
| `result` | array<any> |  |  (example: `[]`) |
| `success` | boolean |  |  (example: `true`) |

<details><summary>Example / shape</summary>

```json
{
  "message": "قطع اتصال کیف پول با موفقیت انجام شد",
  "result": [],
  "success": true
}
```

</details>
