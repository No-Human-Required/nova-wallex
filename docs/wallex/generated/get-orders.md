<!-- source: https://developers.wallex.ir/docs/generated/get-orders -->

# List margin orders

`GET /margin-trade/v1/orders`

**Base URL:** `https://api.wallex.ir`

List margin orders

**Tags:** margin

## Authentication

- `ApiKeyAuth` — apiKey in header `x-api-key`

## Parameters

| Name | In | Type | Required | Description |
| --- | --- | --- | --- | --- |
| `active` | query | boolean |  | List active/inactive orders |
| `market` | query | string |  | Market symbol |
| `position_side` | query | string |  | Position side (long/short) |
| `position_id` | query | string |  | Position ID |
| `position_type` | query | string |  | Position type |
| `side` | query | string |  | Order side |

## Responses

### 200 — scheme of `result` field in success response

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `[].created_at` | string |  |  |
| `[].fee` | object |  |  |
| `[].fee.currency` | string |  |  |
| `[].fee.value` | string |  |  |
| `[].filled` | object |  |  |
| `[].filled.currency` | string |  |  |
| `[].filled.value` | string |  |  |
| `[].filled_price` | object |  |  |
| `[].filled_price.currency` | string |  |  |
| `[].filled_price.value` | string |  |  |
| `[].id` | string |  |  |
| `[].market` | string |  |  |
| `[].price` | object |  |  |
| `[].price.currency` | string |  |  |
| `[].price.value` | string |  |  |
| `[].side` | string |  |  |
| `[].status` | string |  |  |
| `[].trades` | array<object> |  |  |
| `[].trades[].created_at` | string |  |  |
| `[].trades[].fee` | object |  |  |
| `[].trades[].fee.currency` | string |  |  |
| `[].trades[].fee.value` | string |  |  |
| `[].trades[].price` | object |  |  |
| `[].trades[].price.currency` | string |  |  |
| `[].trades[].price.value` | string |  |  |
| `[].trades[].volume` | object |  |  |
| `[].trades[].volume.currency` | string |  |  |
| `[].trades[].volume.value` | string |  |  |
| `[].volume` | object |  |  |
| `[].volume.currency` | string |  |  |
| `[].volume.value` | string |  |  |

<details><summary>Example / shape</summary>

```json
[
  {
    "created_at": "string",
    "fee": {
      "currency": "string",
      "value": "string"
    },
    "filled": {
      "currency": "string",
      "value": "string"
    },
    "filled_price": {
      "currency": "string",
      "value": "string"
    },
    "id": "string",
    "market": "string",
    "price": {
      "currency": "string",
      "value": "string"
    },
    "side": "string",
    "status": "string",
    "trades": [
      {
        "created_at": "string",
        "fee": {
          "currency": "string",
          "value": "string"
        },
        "price": {
          "currency": "string",
          "value": "string"
        },
        "volume": {
          "currency": "string",
          "value": "string"
        }
      }
    ],
    "volume": {
      "currency": "string",
      "value": "string"
    }
  }
]
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
