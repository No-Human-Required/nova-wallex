<!-- source: https://developers.wallex.ir/docs/generated/get-markets -->

# Get all markets 

`GET /hector/web/v1/markets`

**Base URL:** `https://api.wallex.com`

Retrieve  all markets

**Tags:** basic-services

## Authentication

- `ApiKeyAuth` — apiKey in header `x-api-key`

## Responses

### 200 — OK

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `success` | boolean |  |  (example: `true`) |
| `message` | string |  |  (example: `"The operation was successful"`) |
| `result` | object |  |  |
| `result.markets` | array<object> |  |  |
| `result.markets[].symbol` | string |  |  |
| `result.markets[].base_asset` | string |  |  |
| `result.markets[].quote_asset` | string |  |  |
| `result.markets[].fa_base_asset` | string |  |  |
| `result.markets[].fa_quote_asset` | string |  |  |
| `result.markets[].en_base_asset` | string |  |  |
| `result.markets[].en_quote_asset` | string |  |  |
| `result.markets[].categories` | array<integer> |  |  |
| `result.markets[].price` | string |  |  |
| `result.markets[].change_24h` | number <float> |  |  |
| `result.markets[].volume_24h` | number <float> |  |  |
| `result.markets[].change_7D` | number <float> |  |  |
| `result.markets[].quote_volume_24h` | number <float> |  |  |
| `result.markets[].spot_is_new` | boolean |  |  |
| `result.markets[].otc_is_new` | boolean |  |  |
| `result.markets[].is_new` | boolean |  |  |
| `result.markets[].is_spot` | boolean |  |  |
| `result.markets[].is_otc` | boolean |  |  |
| `result.markets[].is_margin` | boolean |  |  |
| `result.markets[].is_tmn_based` | boolean |  |  |
| `result.markets[].is_usdt_based` | boolean |  |  |
| `result.markets[].is_zero_fee` | boolean |  |  |
| `result.markets[].leverage_step` | number <float> |  |  |
| `result.markets[].max_leverage` | number |  |  |
| `result.markets[].created_at` | string <date-time> |  |  |
| `result.markets[].amount_precision` | integer |  |  |
| `result.markets[].price_precision` | integer |  |  |
| `result.markets[].flags` | array<any> |  |  |

<details><summary>Example / shape</summary>

```json
{
  "success": true,
  "message": "The operation was successful",
  "result": {
    "markets": [
      {
        "symbol": "string",
        "base_asset": "string",
        "quote_asset": "string",
        "fa_base_asset": "string",
        "fa_quote_asset": "string",
        "en_base_asset": "string",
        "en_quote_asset": "string",
        "categories": [
          0
        ],
        "price": "string",
        "change_24h": 0,
        "volume_24h": 0,
        "change_7D": 0,
        "quote_volume_24h": 0,
        "spot_is_new": true,
        "otc_is_new": true,
        "is_new": true,
        "is_spot": true,
        "is_otc": true,
        "is_margin": true,
        "is_tmn_based": true,
        "is_usdt_based": true,
        "is_zero_fee": true,
        "leverage_step": 0,
        "max_leverage": 0,
        "created_at": "string",
        "amount_precision": 0,
        "price_precision": 0,
        "flags": [
          null
        ]
      }
    ]
  }
}
```

</details>
