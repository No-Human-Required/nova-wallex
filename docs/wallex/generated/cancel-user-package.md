<!-- source: https://developers.wallex.ir/docs/generated/cancel-user-package -->

# Cancel User Package

`DELETE /v1/prop/user/packages`

**Base URL:** `https://api.wallex.ir`

# DELETE /v1/prop/user/packages

This endpoint cancels a user package based on sub account.

## Headers

- `Sub-Account-Client-id` (string)


## Request Body Parameters

This request does not require a request body.

## Query Parameters

This request does not require any query parameters.

## Response

- `result` (object)

    - `client_id` (string)

    - `start_balance` (string)

    - `final_balance` (string)

    - `final_balance_without_transfers` (string)

    - `currency` (string)

    - `prop_package_id` (number)

    - `user_id` (string)

- `message` (string)

- `success` (boolean)


## Example Response

``` json
{
    "result": {
        "client_id": "testClientId",
        "start_balance": "201000000",
        "final_balance": "201000000",
        "final_balance_without_transfers": "201000000",
        "currency": "TMN",
        "prop_package_id": 69,
        "user_id": "testUserId"
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
| `sub-account-client-id` | header | string |  |  |

## Responses

### 200 — 200

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `message` | string |  |  (example: `"عملیات با موفقیت انجام شد"`) |
| `result` | object |  |  |
| `result.client_id` | string |  |  (example: `"testClientId"`) |
| `result.currency` | string |  |  (example: `"TMN"`) |
| `result.final_balance` | string |  |  (example: `"201000000"`) |
| `result.final_balance_without_transfers` | string |  |  (example: `"201000000"`) |
| `result.prop_package_id` | number |  |  (example: `69`) |
| `result.start_balance` | string |  |  (example: `"201000000"`) |
| `result.user_id` | string |  |  (example: `"testUserId"`) |
| `success` | boolean |  |  (example: `true`) |

<details><summary>Example / shape</summary>

```json
{
  "message": "عملیات با موفقیت انجام شد",
  "result": {
    "client_id": "testClientId",
    "currency": "TMN",
    "final_balance": "201000000",
    "final_balance_without_transfers": "201000000",
    "prop_package_id": 69,
    "start_balance": "201000000",
    "user_id": "testUserId"
  },
  "success": true
}
```

</details>
