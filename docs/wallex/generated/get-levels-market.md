<!-- source: https://developers.wallex.ir/docs/generated/get-levels-market -->

# margin trade user levels

`GET /margin-trade/v1/user/levels/{market}`

**Base URL:** `https://api.wallex.ir`

margin trade user levels

**Tags:** margin

## Authentication

- `ApiKeyAuth` — apiKey in header `x-api-key`

## Parameters

| Name | In | Type | Required | Description |
| --- | --- | --- | --- | --- |
| `market` | path | string | yes | market e.g. USDTTMN |

## Responses

### 200 — scheme of `result` field in success response

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `levels` | object |  |  |
| `levels.{key}.base` | string |  |  |
| `levels.{key}.level` | integer |  |  |
| `levels.{key}.max_loan_volume` | number |  |  |
| `levels.{key}.max_position_volume` | number |  |  |
| `levels.{key}.max_risk_coefficient` | number |  |  |
| `levels.{key}.min_trade_volume` | number |  |  |
| `levels.{key}.quote` | string |  |  |
| `user_level` | integer |  |  |

<details><summary>Example / shape</summary>

```json
{
  "levels": {
    "<key>": {
      "base": "string",
      "level": 0,
      "max_loan_volume": 0,
      "max_position_volume": 0,
      "max_risk_coefficient": 0,
      "min_trade_volume": 0,
      "quote": "string"
    }
  },
  "user_level": 0
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
