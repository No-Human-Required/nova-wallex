<!-- source: https://developers.wallex.ir/docs/generated/post-account-orders -->

# Submit a new trading order

`POST /v1/account/orders`

**Base URL:** `https://api.wallex.com`

Create a new order for trading with specified parameters

**Tags:** spot

## Authentication

- `ApiKeyAuth` — apiKey in header `x-api-key`

## Request body

Order details (required)

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `client_id` | string |  |  |
| `price` | string |  |  |
| `quantity` | string |  |  |
| `side` | string | yes |  |
| `stop_Price` | string |  |  |
| `symbol` | string | yes |  |
| `type` | string | yes |  |

**Example:**

```json
{
  "client_id": "string",
  "price": "string",
  "quantity": "string",
  "side": "string",
  "stop_Price": "string",
  "symbol": "string",
  "type": "string"
}
```

## Responses

### 201 — Order created successfully

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `message` | string |  |  |
| `result` | object |  |  |
| `result.active` | boolean |  |  |
| `result.clientOrderId` | string |  |  |
| `result.created_at` | string |  |  |
| `result.executedPercent` | integer |  |  |
| `result.executedPrice` | string |  |  |
| `result.executedQty` | string |  |  |
| `result.executedSum` | string |  |  |
| `result.fee` | string |  |  |
| `result.fills` | array<object> |  |  |
| `result.fills[].fee` | string |  |  |
| `result.fills[].feeAsset` | string |  |  |
| `result.fills[].feeCoefficient` | string |  |  |
| `result.fills[].isBuyer` | boolean |  |  |
| `result.fills[].makerFeeCoefficient` | string |  |  |
| `result.fills[].price` | string |  |  |
| `result.fills[].quantity` | string |  |  |
| `result.fills[].sum` | string |  |  |
| `result.fills[].symbol` | string |  |  |
| `result.fills[].takerFeeCoefficient` | string |  |  |
| `result.fills[].timestamp` | string |  |  |
| `result.origQty` | string |  |  |
| `result.price` | string |  |  |
| `result.side` | string |  |  |
| `result.status` | string |  |  |
| `result.stopPrice` | string |  |  |
| `result.stopPriceCondition` | string |  |  |
| `result.sum` | string |  |  |
| `result.symbol` | string |  |  |
| `result.transactTime` | integer |  |  |
| `result.type` | string |  |  |
| `result.updated_at` | string |  |  |
| `success` | boolean |  |  |

<details><summary>Example / shape</summary>

```json
{
  "message": "string",
  "result": {
    "active": true,
    "clientOrderId": "string",
    "created_at": "string",
    "executedPercent": 0,
    "executedPrice": "string",
    "executedQty": "string",
    "executedSum": "string",
    "fee": "string",
    "fills": [
      {
        "fee": "string",
        "feeAsset": "string",
        "feeCoefficient": "string",
        "isBuyer": true,
        "makerFeeCoefficient": "string",
        "price": "string",
        "quantity": "string",
        "sum": "string",
        "symbol": "string",
        "takerFeeCoefficient": "string",
        "timestamp": "string"
      }
    ],
    "origQty": "string",
    "price": "string",
    "side": "string",
    "status": "string",
    "stopPrice": "string",
    "stopPriceCondition": "string",
    "sum": "string",
    "symbol": "string",
    "transactTime": 0,
    "type": "string",
    "updated_at": "string"
  },
  "success": true
}
```

</details>

### 400 — Invalid request parameters

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
    "<key>": [
      null
    ]
  },
  "success": true
}
```

</details>

### 401 — Unauthorized

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
    "<key>": [
      null
    ]
  },
  "success": true
}
```

</details>

### 422 — Validation error

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
    "<key>": [
      null
    ]
  },
  "success": true
}
```

</details>
