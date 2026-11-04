<!-- source: https://developers.wallex.ir/docs/generated/candle-history -->

# Get historical market data (candles)

`GET /v1/udf/history`

**Base URL:** `https://api.wallex.com`

Retrieve historical OHLCV data for a symbol. Useful for charting and analysis.

**Tags:** basic-services

## Authentication

- `ApiKeyAuth` — apiKey in header `x-api-key`

## Parameters

| Name | In | Type | Required | Description |
| --- | --- | --- | --- | --- |
| `symbol` | query | string | yes | The symbol to retrieve historical data for (example: `BTCTMN`) |
| `resolution` | query | string | yes | Candle resolution (e.g. 1, 5, 15, 60, D) (example: `60`) |
| `from` | query | integer <int64> | yes | Start of time range (Unix timestamp) (example: `1733425200`) |
| `to` | query | integer <int64> | yes | End of time range (Unix timestamp) (example: `1733428800`) |

## Responses

### 200 — Successful response

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `s` | string |  |  (example: `"ok"`) |
| `t` | array<integer <int64>> |  |  (example: `[1733425200, 1733428800]`) |
| `c` | array<string> |  |  (example: `["7209722048.0000000000000000", "7235725819.0000000000000000"]`) |
| `o` | array<string> |  |  (example: `["7286137604.0000000000000000", "7200151050.0000000000000000"]`) |
| `h` | array<string> |  |  (example: `["7286137604.0000000000000000", "7235725819.0000000000000000"]`) |
| `l` | array<string> |  |  (example: `["7209722048.0000000000000000", "7150000001.0000000000000000"]`) |
| `v` | array<string> |  |  (example: `["0.2544820000000000", "1.0201680000000000"]`) |

<details><summary>Example / shape</summary>

```json
{
  "s": "ok",
  "t": [
    1733425200,
    1733428800
  ],
  "c": [
    "7209722048.0000000000000000",
    "7235725819.0000000000000000"
  ],
  "o": [
    "7286137604.0000000000000000",
    "7200151050.0000000000000000"
  ],
  "h": [
    "7286137604.0000000000000000",
    "7235725819.0000000000000000"
  ],
  "l": [
    "7209722048.0000000000000000",
    "7150000001.0000000000000000"
  ],
  "v": [
    "0.2544820000000000",
    "1.0201680000000000"
  ]
}
```

</details>
