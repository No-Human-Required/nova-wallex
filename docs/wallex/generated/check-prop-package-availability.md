<!-- source: https://developers.wallex.ir/docs/generated/check-prop-package-availability -->

# Check Prop Package Availability

`GET /v1/prop/user/packages/{id}/check-availability`

**Base URL:** `https://api.wallex.ir`

# GET /v1/prop/user/packages/{id}/check-availability

This endpoint checks the availability of a prop package for a user based on different criteria.

## Headers

This request does not require any custom header.

## Request Body Parameters

This request does not require a request body.

## Query Parameters

This request does not require any query parameters.

## Response

- `result` (array\[object\])

    - `key` (string)

    - `isValid` (boolean)

- `message` (string)
- `success`

## Example Response

``` json
{
    "result": [
        {
            "key": "kyc",
            "isValid": true
        }
    ],
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
| `id` | path | string | yes |  |

## Responses

### 200 — 200

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `message` | string |  |  (example: `"عملیات با موفقیت انجام شد"`) |
| `result` | array<object> |  |  (example: `[{"isValid": true, "key": "kyc"}]`) |
| `result[].isValid` | boolean |  |  (example: `true`) |
| `result[].key` | string |  |  (example: `"kyc"`) |
| `success` | boolean |  |  (example: `true`) |

<details><summary>Example / shape</summary>

```json
{
  "message": "عملیات با موفقیت انجام شد",
  "result": [
    {
      "isValid": true,
      "key": "kyc"
    }
  ],
  "success": true
}
```

</details>
