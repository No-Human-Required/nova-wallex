<!-- source: https://developers.wallex.ir/docs/generated/profit-position-id -->

# Calculate

`POST /margin-trade/v1/positions/{id}/profit`

**Base URL:** `https://api.wallex.ir`

Calculate

**Tags:** margin

## Authentication

- `ApiKeyAuth` — apiKey in header `x-api-key`

## Parameters

| Name | In | Type | Required | Description |
| --- | --- | --- | --- | --- |
| `id` | path | string | yes | Position ID |

## Request body

Request body (required)

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `close_price` | string |  |  |
| `strategy` | string |  |  |

**Example:**

```json
{
  "close_price": "string",
  "strategy": "string"
}
```

## Responses

### 200 — scheme of `result` field in success response

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `fee` | string |  |  |
| `filled_percentage` | string |  |  |
| `interest` | object |  |  |
| `interest.currency` | string |  |  |
| `interest.value` | string |  |  |
| `price` | string |  |  |
| `profit` | object |  |  |
| `profit.currency` | string |  |  |
| `profit.value` | string |  |  |
| `side` | string |  |  |
| `volume` | object |  |  |
| `volume.currency` | string |  |  |
| `volume.value` | string |  |  |

<details><summary>Example / shape</summary>

```json
{
  "fee": "string",
  "filled_percentage": "string",
  "interest": {
    "currency": "string",
    "value": "string"
  },
  "price": "string",
  "profit": {
    "currency": "string",
    "value": "string"
  },
  "side": "string",
  "volume": {
    "currency": "string",
    "value": "string"
  }
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
