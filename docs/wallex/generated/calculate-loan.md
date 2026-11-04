<!-- source: https://developers.wallex.ir/docs/generated/calculate-loan -->

# calculate min, max Collateral and loan

`POST /margin-trade/v1/public/loan`

**Base URL:** `https://api.wallex.ir`

calculate min, max Collateral and loan

**Tags:** margin

## Authentication

- `ApiKeyAuth` — apiKey in header `x-api-key`

## Request body

Request body (required)

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `collateral` | string |  |  |
| `market` | string |  |  |
| `open_price` | string |  |  |
| `risk_coef` | string |  |  |
| `side` | string |  |  |

**Example:**

```json
{
  "collateral": "string",
  "market": "string",
  "open_price": "string",
  "risk_coef": "string",
  "side": "string"
}
```

## Responses

### 200 — scheme of `result` field in success response

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `collateral` | object |  |  |
| `collateral.max` | string |  |  |
| `collateral.min` | string |  |  |
| `loan` | object |  |  |
| `loan.currency` | string |  |  |
| `loan.value` | string |  |  |

<details><summary>Example / shape</summary>

```json
{
  "collateral": {
    "max": "string",
    "min": "string"
  },
  "loan": {
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
