<!-- source: https://developers.wallex.ir/docs/generated/get-pnl -->

# User PNL

`GET /margin-trade/v1/user/pnl`

**Base URL:** `https://api.wallex.ir`

User PNL

**Tags:** margin

## Authentication

- `ApiKeyAuth` — apiKey in header `x-api-key`

## Responses

### 200 — scheme of `result` field in success response

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `collaterals` | object |  |  |
| `loans` | object |  |  |
| `profits` | object |  |  |
| `total` | object |  |  |

<details><summary>Example / shape</summary>

```json
{
  "collaterals": {
    "<key>": 0
  },
  "loans": {
    "<key>": 0
  },
  "profits": {
    "<key>": 0
  },
  "total": {
    "<key>": 0
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
