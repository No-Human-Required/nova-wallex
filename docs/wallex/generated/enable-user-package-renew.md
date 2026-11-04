<!-- source: https://developers.wallex.ir/docs/generated/enable-user-package-renew -->

# Enable User Package Renew

`POST /v1/prop/user/packages/enable-renew`

**Base URL:** `https://api.wallex.ir`

# POST /v1/prop/user/packages/enable-renew

This endpoint enables renewal for a user package based on sub account.

## Headers

- `Sub-Account-Client-id` (string)


## Request Body Parameters

This request does not require any body parameters.

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

## Request body

Content-Type: `application/json`

_(no fields)_

## Responses

### 200 — 200

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `message` | string |  |  (example: `"عملیات با موفقیت انجام شد"`) |
| `result` | array<any> |  |  (example: `[]`) |
| `success` | boolean |  |  (example: `true`) |

<details><summary>Example / shape</summary>

```json
{
  "message": "عملیات با موفقیت انجام شد",
  "result": [],
  "success": true
}
```

</details>
