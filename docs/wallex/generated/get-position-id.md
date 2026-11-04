<!-- source: https://developers.wallex.ir/docs/generated/get-position-id -->

# Get a margin position

`GET /margin-trade/v1/positions/{id}`

**Base URL:** `https://api.wallex.ir`

Get a margin position

**Tags:** margin

## Authentication

- `ApiKeyAuth` — apiKey in header `x-api-key`

## Parameters

| Name | In | Type | Required | Description |
| --- | --- | --- | --- | --- |
| `id` | path | string | yes | Position ID |

## Responses

### 200 — scheme of `result` field in success response

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `call_price` | string |  |  |
| `close_filled_price` | string |  |  |
| `close_price` | string |  |  |
| `close_reason` | string |  |  |
| `closed_at` | string |  |  |
| `collateral` | object |  |  |
| `collateral.currency` | string |  |  |
| `collateral.value` | string |  |  |
| `created_at` | string |  |  |
| `expires_at` | string |  |  |
| `extend_time` | integer |  |  |
| `first_order_filled` | boolean |  |  |
| `id` | string |  |  |
| `interest` | object |  |  |
| `interest.currency` | string |  |  |
| `interest.value` | string |  |  |
| `is_called` | boolean |  |  |
| `liquidity_price` | string |  |  |
| `loan` | object |  |  |
| `loan.currency` | string |  |  |
| `loan.value` | string |  |  |
| `market` | string |  |  |
| `max_age` | integer |  |  |
| `open_filled_price` | string |  |  |
| `open_price` | string |  |  |
| `opened_at` | string |  |  |
| `profit` | object |  |  |
| `profit.currency` | string |  |  |
| `profit.value` | string |  |  |
| `profit_percentage` | string |  |  |
| `risk_coef` | string |  |  |
| `side` | string |  |  |
| `state` | string |  |  |
| `stop_loss` | string |  |  |
| `take_profit` | string |  |  |
| `updated_at` | string |  |  |

<details><summary>Example / shape</summary>

```json
{
  "call_price": "string",
  "close_filled_price": "string",
  "close_price": "string",
  "close_reason": "string",
  "closed_at": "string",
  "collateral": {
    "currency": "string",
    "value": "string"
  },
  "created_at": "string",
  "expires_at": "string",
  "extend_time": 0,
  "first_order_filled": true,
  "id": "string",
  "interest": {
    "currency": "string",
    "value": "string"
  },
  "is_called": true,
  "liquidity_price": "string",
  "loan": {
    "currency": "string",
    "value": "string"
  },
  "market": "string",
  "max_age": 0,
  "open_filled_price": "string",
  "open_price": "string",
  "opened_at": "string",
  "profit": {
    "currency": "string",
    "value": "string"
  },
  "profit_percentage": "string",
  "risk_coef": "string",
  "side": "string",
  "state": "string",
  "stop_loss": "string",
  "take_profit": "string",
  "updated_at": "string"
}
```

</details>

### 404 — Not Found

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
