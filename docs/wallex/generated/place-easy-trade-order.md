<!-- source: https://developers.wallex.ir/docs/generated/place-easy-trade-order -->

# create otc trade

`POST /v1/account/easy-trade/orders`

**Base URL:** `https://api.wallex.ir`

create otc order

**Tags:** otc

## Authentication

- `ApiKeyAuth` — apiKey in header `x-api-key`

## Request body

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `symbol` | string | yes |  (example: `"BTCTMN"`) |
| `side` | string (BUY | SELL) | yes |  (example: `"BUY"`) |
| `quantity` | number <float> | yes |  (example: `2.9e-05`) |
| `from` | string | yes |  (example: `"otc"`) |

**Example:**

```json
{
  "symbol": "BTCTMN",
  "side": "BUY",
  "quantity": 2.9e-05,
  "from": "otc"
}
```

## Responses

### 201 — پاسخ موفق

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `symbol` | string |  |  (example: `"BTCTMN"`) |
| `sourceMarket` | string |  |  (example: `"BTC"`) |
| `destinationMarket` | string |  |  (example: `"TMN"`) |
| `type` | string |  |  (example: `"OTC"`) |
| `side` | string |  |  (example: `"BUY"`) |
| `clientOrderId` | string |  |  (example: `"OTC-9f5fa3c6-b663-4e05-be4c-3c9ad06ee492"`) |
| `transactTime` | integer <int64> |  |  (example: `1752331184`) |
| `price` | string |  |  (example: `"10062689383.4710000000000000"`) |
| `origQty` | string |  |  (example: `"0.0000290000000000"`) |
| `executedSum` | string |  |  (example: `"291817.9921206590000000"`) |
| `executedQty` | string |  |  (example: `"0.0000290000000000"`) |
| `executedPrice` | string |  |  (example: `"10062689383.4710000000000000"`) |
| `sum` | string |  |  (example: `"291817.9921206590000000"`) |
| `executedPercent` | number |  |  (example: `100`) |
| `status` | string |  |  (example: `"FILLED"`) |
| `active` | boolean |  |  (example: `false`) |
| `fills` | array<object> |  |  |
| `fills[].price` | string |  |  (example: `"10062689383.4710000000000000"`) |
| `fills[].quantity` | string |  |  (example: `"0.0000290000000000"`) |
| `fills[].fee` | string |  |  (example: `"0.000000"`) |
| `fills[].feeCoefficient` | string |  |  (example: `"0.0000000000000000"`) |
| `fills[].feeAsset` | object |  |  |
| `fills[].timestamp` | string <date-time> |  |  (example: `"2025-07-12T14:39:44Z"`) |
| `fills[].symbol` | string |  |  (example: `"BTCTMN"`) |
| `fills[].sum` | string |  |  (example: `"291817.9921206590000000"`) |
| `fills[].makerFeeCoefficient` | string |  |  (example: `"0"`) |
| `fills[].takerFeeCoefficient` | string |  |  (example: `"0"`) |
| `fills[].isBuyer` | boolean |  |  (example: `true`) |

<details><summary>Example / shape</summary>

```json
{
  "symbol": "BTCTMN",
  "sourceMarket": "BTC",
  "destinationMarket": "TMN",
  "type": "OTC",
  "side": "BUY",
  "clientOrderId": "OTC-9f5fa3c6-b663-4e05-be4c-3c9ad06ee492",
  "transactTime": 1752331184,
  "price": "10062689383.4710000000000000",
  "origQty": "0.0000290000000000",
  "executedSum": "291817.9921206590000000",
  "executedQty": "0.0000290000000000",
  "executedPrice": "10062689383.4710000000000000",
  "sum": "291817.9921206590000000",
  "executedPercent": 100,
  "status": "FILLED",
  "active": false,
  "fills": [
    {
      "price": "10062689383.4710000000000000",
      "quantity": "0.0000290000000000",
      "fee": "0.000000",
      "feeCoefficient": "0.0000000000000000",
      "feeAsset": {},
      "timestamp": "2025-07-12T14:39:44Z",
      "symbol": "BTCTMN",
      "sum": "291817.9921206590000000",
      "makerFeeCoefficient": "0",
      "takerFeeCoefficient": "0",
      "isBuyer": true
    }
  ]
}
```

</details>
