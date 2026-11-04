<!-- source: https://developers.wallex.ir/docs/generated/get-open-order -->

# List active orders

`GET /v1/account/openOrders`

**Base URL:** `https://api.wallex.com`

Get a list of currently active orders

**Tags:** spot

## Authentication

- `ApiKeyAuth` — apiKey in header `x-api-key`

## Parameters

| Name | In | Type | Required | Description |
| --- | --- | --- | --- | --- |
| `symbol` | query | string |  | Market symbol |
| `page` | query | integer |  | Page number (default: 1) |
| `per_page` | query | integer |  | Items per page |

## Responses

### 200 — OK

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `message` | string |  |  |
| `result` | object |  |  |
| `result_info` | any |  |  |
| `success` | boolean |  |  |

<details><summary>Example / shape</summary>

```json
{
  "message": "string",
  "result": {
    "<key>": [
      {
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
      }
    ]
  },
  "result_info": null,
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
