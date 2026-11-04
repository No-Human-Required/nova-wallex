<!-- source: https://developers.wallex.ir/docs/generated/get-depth -->

# Get all markets depth

`GET /depth/all`

**Base URL:** `https://api.wallex.com`

Retrieve market depth for all markets

**Tags:** spot

## Responses

### 200 — OK

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `message` | string |  |  |
| `result` | object |  |  |
| `result.{key}.ask` | array<object> |  |  |
| `result.{key}.ask[].price` | number |  |  |
| `result.{key}.ask[].quantity` | number |  |  |
| `result.{key}.ask[].sum` | number |  |  |
| `result.{key}.bid` | array<object> |  |  |
| `result.{key}.bid[].price` | number |  |  |
| `result.{key}.bid[].quantity` | number |  |  |
| `result.{key}.bid[].sum` | number |  |  |
| `success` | boolean |  |  |

<details><summary>Example / shape</summary>

```json
{
  "message": "string",
  "result": {
    "<key>": {
      "ask": [
        {
          "price": 0,
          "quantity": 0,
          "sum": 0
        }
      ],
      "bid": [
        {
          "price": 0,
          "quantity": 0,
          "sum": 0
        }
      ]
    }
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
    "<key>": [
      null
    ]
  },
  "success": true
}
```

</details>
