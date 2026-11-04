<!-- source: https://developers.wallex.ir/docs/generated/get-otc-markets -->

# get otc markets

`GET /v1/otc/markets`

**Base URL:** `https://api.wallex.ir`

retrieves markets which are enabled in otc

**Tags:** otc

## Authentication

- `ApiKeyAuth` — apiKey in header `x-api-key`

## Responses

### 200 — پاسخ موفق

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `success` | boolean |  |  (example: `true`) |
| `message` | string |  |  (example: `"عملیات با موفقیت انجام شد"`) |
| `result` | object |  |  |
| `result.{key}.symbol` | string |  |  (example: `"BTCUSDT"`) |
| `result.{key}.baseAsset` | string |  |  (example: `"BTC"`) |
| `result.{key}.baseAsset_png_icon` | string <uri> |  |  |
| `result.{key}.baseAsset_svg_icon` | string <uri> |  |  |
| `result.{key}.baseAssetPrecision` | integer |  |  (example: `8`) |
| `result.{key}.quoteAsset` | string |  |  (example: `"USDT"`) |
| `result.{key}.quoteAsset_png_icon` | string <uri> |  |  |
| `result.{key}.quoteAsset_svg_icon` | string <uri> |  |  |
| `result.{key}.quotePrecision` | integer |  |  (example: `8`) |
| `result.{key}.faName` | string |  |  (example: `"بیت کوین - تتر"`) |
| `result.{key}.enName` | string |  |  (example: `"Bitcoin - Tether"`) |
| `result.{key}.faBaseAsset` | string |  |  (example: `"بیت کوین"`) |
| `result.{key}.enBaseAsset` | string |  |  (example: `"Bitcoin"`) |
| `result.{key}.faQuoteAsset` | string |  |  (example: `"تتر"`) |
| `result.{key}.enQuoteAsset` | string |  |  (example: `"Tether"`) |
| `result.{key}.stepSize` | integer |  |  (example: `2`) |
| `result.{key}.tickSize` | integer |  |  (example: `0`) |
| `result.{key}.minQty` | number <float> |  |  (example: `0.01`) |
| `result.{key}.minNotional` | number <float> |  |  (example: `90000`) |
| `result.{key}.maxNotional` | number <float> |  |  (example: `50000000`) |
| `result.{key}.stats` | object |  |  |
| `result.{key}.stats.24h_ch` | number <float> |  |  (example: `-0.56`) |
| `result.{key}.stats.lastPrice` | number <float> |  |  (example: `116795.22`) |
| `result.{key}.stats.24h_highPrice` | number <float> |  |  (example: `118679`) |
| `result.{key}.stats.24h_lowPrice` | number <float> |  |  (example: `115000`) |
| `result.{key}.stats.24h_volume` | number <float> |  |  (example: `0`) |
| `result.{key}.buyStatus` | string (ENABLE | DISABLE) |  |  (example: `"ENABLE"`) |
| `result.{key}.sellStatus` | string (ENABLE | DISABLE) |  |  (example: `"ENABLE"`) |
| `result.{key}.exchangeStatus` | string (ENABLE | DISABLE) |  |  (example: `"ENABLE"`) |
| `result.{key}.createdAt` | string <date-time> |  |  |
| `result.{key}.isNew` | boolean |  |  (example: `false`) |
| `result.{key}.isZeroFee` | boolean |  |  (example: `false`) |
| `result.{key}.flags` | array<any> |  |  |

<details><summary>Example / shape</summary>

```json
{
  "success": true,
  "message": "عملیات با موفقیت انجام شد",
  "result": {
    "<key>": {
      "symbol": "BTCUSDT",
      "baseAsset": "BTC",
      "baseAsset_png_icon": "string",
      "baseAsset_svg_icon": "string",
      "baseAssetPrecision": 8,
      "quoteAsset": "USDT",
      "quoteAsset_png_icon": "string",
      "quoteAsset_svg_icon": "string",
      "quotePrecision": 8,
      "faName": "بیت کوین - تتر",
      "enName": "Bitcoin - Tether",
      "faBaseAsset": "بیت کوین",
      "enBaseAsset": "Bitcoin",
      "faQuoteAsset": "تتر",
      "enQuoteAsset": "Tether",
      "stepSize": 2,
      "tickSize": 0,
      "minQty": 0.01,
      "minNotional": 90000,
      "maxNotional": 50000000,
      "stats": {
        "24h_ch": -0.56,
        "lastPrice": 116795.22,
        "24h_highPrice": 118679,
        "24h_lowPrice": 115000,
        "24h_volume": 0
      },
      "buyStatus": "ENABLE",
      "sellStatus": "ENABLE",
      "exchangeStatus": "ENABLE",
      "createdAt": "string",
      "isNew": false,
      "isZeroFee": false,
      "flags": [
        null
      ]
    }
  }
}
```

</details>
