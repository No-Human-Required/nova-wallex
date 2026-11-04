<!-- source: https://developers.wallex.ir/docs/generated/prop-package-details -->

# Prop Package Details

`GET /v1/prop/packages/{id}`

**Base URL:** `https://api.wallex.ir`

# GET v1/prop/packages/{id}

This endpoint retrieves the details for a prop package.

## Headers

This request does not require any custom header.

## Request Body Parameters

This request does not require a request body.

## Query Parameters

This request does not require any query parameters.

## Response

The response for this request is a JSON object with the following properties:

- `result` (object)

    - `detail` (number)

        - `id` (string)

        - `title` (string)

        - `currency` (string)

        - `destination_currency` (string)

        - `assurance` (string)

        - `loan` (string)

        - `warning_limit` (string)

        - `liquidity_limit` (string)

        - `status` (string)

        - `expire_days` (number)

        - `dark_image_url` (string)

        - `light_image_url` (string)

        - `daily_fee` (string)

        - `daily_fee_discount` (string)

        - `daily_fee_after_discount` (string)

        - `final_fee` (string)

        - `final_fee_discount` (string)

        - `final_fee_after_discount` (string)

    - `unavailableMarkets` (array\[string\])

    - faq (array\[string\])

- `message` (string)
- `success` (boolean)

## Example Response

``` json
{
    "result": {
        "detail": {
            "id": 147,
            "title": "600 میلیون اعتبار معاملاتی",
            "currency": "TMN",
            "destination_currency": null,
            "assurance": "60000000",
            "loan": "600000000",
            "warning_limit": "642000000",
            "liquidity_limit": "624000000",
            "status": "INACTIVE",
            "expire_days": 30,
            "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/QrOWJudTqCA4BxKlRZ99vFcnkUG5SEWNBoK5ayu2.png",
            "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/ceY4TTn6yQXvmUHZvy2g3e5B8zt6sGsI2XAQuhFl.png",
            "daily_fee": "600000",
            "daily_fee_discount": "0",
            "daily_fee_after_discount": "600000",
            "final_fee": "18000000",
            "final_fee_discount": "0",
            "final_fee_after_discount": "18000000"
        },
        "unavailableMarkets": [
            "WTMN",
            "METMN",
            "WUSDT"    
        ],
        "faq": []
    },
    "message": "عملیات با موفقیت انجام شد",
    "success": true
}

 ```

**Tags:** trade-credit

## Authentication

- `x-api-key` — apiKey in header `x-api-key`

## Parameters

| Name | In | Type | Required | Description |
| --- | --- | --- | --- | --- |
| `id` | path | string | yes |  |

## Responses

### 200 — 200

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `message` | string |  |  (example: `"عملیات با موفقیت انجام شد"`) |
| `result` | object |  |  |
| `result.detail` | object |  |  |
| `result.detail.assurance` | string |  |  (example: `"60000000"`) |
| `result.detail.currency` | string |  |  (example: `"TMN"`) |
| `result.detail.daily_fee` | string |  |  (example: `"600000"`) |
| `result.detail.daily_fee_after_discount` | string |  |  (example: `"600000"`) |
| `result.detail.daily_fee_discount` | string |  |  (example: `"0"`) |
| `result.detail.dark_image_url` | string |  |  (example: `"https://s3.thr1.sotoon.ir/wallex-public/packages/QrOWJudTqCA4BxKlRZ99vFcnkUG5SEWNBoK5ayu2.png"`) |
| `result.detail.destination_currency` | any |  |  |
| `result.detail.expire_days` | number |  |  (example: `30`) |
| `result.detail.final_fee` | string |  |  (example: `"18000000"`) |
| `result.detail.final_fee_after_discount` | string |  |  (example: `"18000000"`) |
| `result.detail.final_fee_discount` | string |  |  (example: `"0"`) |
| `result.detail.id` | number |  |  (example: `147`) |
| `result.detail.light_image_url` | string |  |  (example: `"https://s3.thr1.sotoon.ir/wallex-public/packages/ceY4TTn6yQXvmUHZvy2g3e5B8zt6sGsI2XAQuhFl.png"`) |
| `result.detail.liquidity_limit` | string |  |  (example: `"624000000"`) |
| `result.detail.loan` | string |  |  (example: `"600000000"`) |
| `result.detail.status` | string |  |  (example: `"INACTIVE"`) |
| `result.detail.title` | string |  |  (example: `"600 میلیون اعتبار معاملاتی"`) |
| `result.detail.warning_limit` | string |  |  (example: `"642000000"`) |
| `result.faq` | array<any> |  |  (example: `[]`) |
| `result.unavailableMarkets` | array<string> |  |  (example: `["WTMN", "METMN", "WUSDT", "JSTTMN", "JTOTMN", "JUPTMN", "MEUSDT", "BTTCTMN", "FORMTMN", "JSTUSDT", "JTOUSDT", "JUPUSDT", "NEARTMN", "NEXOTMN", "OSMOTMN", "PAXGTMN", "PNUTTMN", "POLSTMN", "PYTHTMN", "RUNETMN", "SAMOTMN", "TAPSTMN", "YFIUSDT", "AIOZUSDT", "BTTCUSDT", "FORMUSDT", "NEARUSDT", "NEXOUSDT", "OSMOUSDT", "PAXGUSDT", "PENGUTMN", "PIXFITMN", "PNUTUSDT", "POLSUSDT", "PYTHUSDT", "RBTCUSDT", "RUNEUSDT", "SAMOUSDT", "TAPSUSDT", "BURGERTMN", "EIGENUSDT", "JASMYUSDT", "PENGUUSDT", "PIXFIUSDT", "BURGERUSDT", "PEOPLEUSDT", "1BBABYDOGETMN", "1BBABYDOGEUSDT"]`) |
| `success` | boolean |  |  (example: `true`) |

<details><summary>Example / shape</summary>

```json
{
  "message": "عملیات با موفقیت انجام شد",
  "result": {
    "detail": {
      "assurance": "60000000",
      "currency": "TMN",
      "daily_fee": "600000",
      "daily_fee_after_discount": "600000",
      "daily_fee_discount": "0",
      "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/QrOWJudTqCA4BxKlRZ99vFcnkUG5SEWNBoK5ayu2.png",
      "destination_currency": null,
      "expire_days": 30,
      "final_fee": "18000000",
      "final_fee_after_discount": "18000000",
      "final_fee_discount": "0",
      "id": 147,
      "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/ceY4TTn6yQXvmUHZvy2g3e5B8zt6sGsI2XAQuhFl.png",
      "liquidity_limit": "624000000",
      "loan": "600000000",
      "status": "INACTIVE",
      "title": "600 میلیون اعتبار معاملاتی",
      "warning_limit": "642000000"
    },
    "faq": [],
    "unavailableMarkets": [
      "WTMN",
      "METMN",
      "WUSDT",
      "JSTTMN",
      "JTOTMN",
      "JUPTMN",
      "MEUSDT",
      "BTTCTMN",
      "FORMTMN",
      "JSTUSDT",
      "JTOUSDT",
      "JUPUSDT",
      "NEARTMN",
      "NEXOTMN",
      "OSMOTMN",
      "PAXGTMN",
      "PNUTTMN",
      "POLSTMN",
      "PYTHTMN",
      "RUNETMN",
      "SAMOTMN",
      "TAPSTMN",
      "YFIUSDT",
      "AIOZUSDT",
      "BTTCUSDT",
      "FORMUSDT",
      "NEARUSDT",
      "NEXOUSDT",
      "OSMOUSDT",
      "PAXGUSDT",
      "PENGUTMN",
      "PIXFITMN",
      "PNUTUSDT",
      "POLSUSDT",
      "PYTHUSDT",
      "RBTCUSDT",
      "RUNEUSDT",
      "SAMOUSDT",
      "TAPSUSDT",
      "BURGERTMN",
      "EIGENUSDT",
      "JASMYUSDT",
      "PENGUUSDT",
      "PIXFIUSDT",
      "BURGERUSDT",
      "PEOPLEUSDT",
      "1BBABYDOGETMN",
      "1BBABYDOGEUSDT"
    ]
  },
  "success": true
}
```

</details>
