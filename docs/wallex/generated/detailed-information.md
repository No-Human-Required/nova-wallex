<!-- source: https://developers.wallex.ir/docs/generated/detailed-information -->

# info a margin position before creation

`POST /margin-trade/v1/public/dry-run`

**Base URL:** `https://api.wallex.ir`

info a margin position before creation

**Tags:** margin

## Authentication

- `ApiKeyAuth` — apiKey in header `x-api-key`

## Request body

Open request body (required)

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `collateral` | string |  |  |
| `market` | string |  |  |
| `open_price` | string |  |  |
| `risk_coef` | string |  |  |
| `side` | string |  |  |
| `stop_loss` | string |  |  |
| `take_profit` | string |  |  |

**Example:**

```json
{
  "collateral": "string",
  "market": "string",
  "open_price": "string",
  "risk_coef": "string",
  "side": "string",
  "stop_loss": "string",
  "take_profit": "string"
}
```

## Responses

### 200 — scheme of `result` field in success response

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `call_price` | string |  |  |
| `collateral` | object |  |  |
| `collateral.currency` | string |  |  |
| `collateral.value` | string |  |  |
| `extend_fee` | object |  |  |
| `extend_fee.currency` | string |  |  |
| `extend_fee.value` | string |  |  |
| `extend_time` | integer |  |  |
| `liquidity_price` | string |  |  |
| `loan` | object |  |  |
| `loan.currency` | string |  |  |
| `loan.value` | string |  |  |
| `market` | string |  |  |
| `max_age` | integer |  |  |
| `open_fee` | object |  |  |
| `open_fee.currency` | string |  |  |
| `open_fee.value` | string |  |  |
| `open_price` | string |  |  |
| `risk_coef` | string |  |  |
| `side` | string |  |  |
| `stop_loss` | string |  |  |
| `take_profit` | string |  |  |
| `trade_fee` | object |  |  |
| `trade_fee.currency` | string |  |  |
| `trade_fee.value` | string |  |  |

<details><summary>Example / shape</summary>

```json
{
  "call_price": "string",
  "collateral": {
    "currency": "string",
    "value": "string"
  },
  "extend_fee": {
    "currency": "string",
    "value": "string"
  },
  "extend_time": 0,
  "liquidity_price": "string",
  "loan": {
    "currency": "string",
    "value": "string"
  },
  "market": "string",
  "max_age": 0,
  "open_fee": {
    "currency": "string",
    "value": "string"
  },
  "open_price": "string",
  "risk_coef": "string",
  "side": "string",
  "stop_loss": "string",
  "take_profit": "string",
  "trade_fee": {
    "currency": "string",
    "value": "string"
  }
}
```

</details>

### 408 — Request time out

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `code` | integer |  |  |
| `message` | string |  |  |
| `result` | object |  |  |
| `success` | boolean |  |  |

<details><summary>Example / shape</summary>

```json
{
  "code": 0,
  "message": "string",
  "result": {
    "<key>": "string"
  },
  "success": true
}
```

</details>

### 500 — Internal server error

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `code` | integer |  |  |
| `message` | string |  |  |
| `result` | object |  |  |
| `success` | boolean |  |  |

<details><summary>Example / shape</summary>

```json
{
  "code": 0,
  "message": "string",
  "result": {
    "<key>": "string"
  },
  "success": true
}
```

</details>
