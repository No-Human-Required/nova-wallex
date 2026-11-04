<!-- source: https://developers.wallex.ir/docs/generated/get-account-balances -->

# Get account balances

`GET /v1/account/balances`

**Base URL:** `https://api.wallex.com`

Retrieve the list of all account balances. Requires API key.

**Tags:** basic-services

## Authentication

- `ApiKeyAuth` — apiKey in header `x-api-key`

## Responses

### 200 — Successful response

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `result` | object |  |  |
| `result.balances` | object |  |  |
| `result.balances.{key}.asset` | string |  |  (example: `"1BBABYDOGE"`) |
| `result.balances.{key}.asset_png_icon` | string <uri> |  |  |
| `result.balances.{key}.asset_svg_icon` | string <uri> |  |  |
| `result.balances.{key}.faName` | string |  |  (example: `"۱میلیارد بیبی دوج"`) |
| `result.balances.{key}.fiat` | boolean |  |  |
| `result.balances.{key}.value` | string |  |  (example: `"13.97200000"`) |
| `result.balances.{key}.locked` | string |  |  (example: `"0.00000000"`) |
| `result.balances.{key}.is_dust` | boolean |  |  |
| `result.balances.{key}.is_digital_gold` | boolean |  |  |
| `message` | string |  |  (example: `"عملیات با موفقیت انجام شد"`) |
| `success` | boolean |  |  (example: `true`) |

<details><summary>Example / shape</summary>

```json
{
  "result": {
    "balances": {
      "<key>": {
        "asset": "1BBABYDOGE",
        "asset_png_icon": "string",
        "asset_svg_icon": "string",
        "faName": "۱میلیارد بیبی دوج",
        "fiat": true,
        "value": "13.97200000",
        "locked": "0.00000000",
        "is_dust": true,
        "is_digital_gold": true
      }
    }
  },
  "message": "عملیات با موفقیت انجام شد",
  "success": true
}
```

</details>
