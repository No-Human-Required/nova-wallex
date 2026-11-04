<!-- source: https://developers.wallex.ir/docs/generated/sub-account-transfer -->

# List Sub Account Transfers

`GET /sub-accounts/transfers`

**Base URL:** `https://api.wallex.ir`

# GET /sub-accounts/transfers

This endpoint retrieves transfer details for a sub-account.

## Headers

This request does not require any custom header.

## Request Body Parameters

This request does not require a request body.

## Query Parameters

This request does not require any query parameters.

## Response

- `result` (array\[object\])

    - `unique_id` (number)

    - `source_client_id` (string)

    - `source_client_title` (string)

    - `destination_client_id` (string)

    - `destination_client_title` (string)

    - `source_user_type` (string)

    - `destination_user_type` (string)

    - `fa_source_user_type` (string)

    - `fa_destination_user_type` (string)

    - `currency` (string)

    - `value` (string)

    - `reason` (string)

    - `createdAt` (string)

- `message` (string)

- `success` (boolean)

- `result_info` (object)

    - `page` (number)

    - `per_page` (number)

    - `count` (number)

    - `total_count` (number)


## Example Response

``` json
{
  "result": [
    {
      "unique_id": 0,
      "source_client_id": "",
      "source_client_title": "",
      "destination_client_id": "",
      "destination_client_title": null,
      "source_user_type": "",
      "destination_user_type": "",
      "fa_source_user_type": "",
      "fa_destination_user_type": "",
      "currency": "",
      "value": "",
      "reason": "",
      "createdAt": ""
    }
  ],
  "message": "",
  "success": true,
  "result_info": {
    "page": 0,
    "per_page": 0,
    "count": 0,
    "total_count": 0
  }
}

 ```

**Tags:** trade-credit

## Authentication

- `x-api-key` — apiKey in header `x-api-key`

## Parameters

| Name | In | Type | Required | Description |
| --- | --- | --- | --- | --- |
| `sub-account-client-id` | header | string |  |  |

## Responses

### 200 — 200

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `message` | string |  |  (example: `"عملیات با موفقیت انجام شد"`) |
| `result` | array<object> |  |  (example: `[{"createdAt": "2025-04-06T11:54:31Z", "currency": "TMN", "destination_client_id": "3", "destination_client_title": null, "destination_user_type": "wallex-to-subrogation", "fa_destination_user_type": "والکس(به‌وکالت)", "fa_source_user_type": "سکوی معامله", "reason": "هزینه عملیات سکو", "source_client_id": "testClientId", "source_client_title": "تست اولیه عادی", "source_user_type": "prop", "unique_id": 7924, "value": "201000000"}, {"createdAt": "2025-04-06T11:54:04Z", "currency": "TMN", "destination_client_id": "testClientId", "destination_client_title": "تست اولیه عادی", "destination_user_type": "prop", "fa_destination_user_type": "سکوی معامله", "fa_source_user_type": "اصلی", "reason": "دارایی ورودی طرح سکو", "source_client_id": "testUserId", "source_client_title": null, "source_user_type": "master", "unique_id": 7922, "value": "1000000"}, {"createdAt": "2025-04-06T11:54:04Z", "currency": "TMN", "destination_client_id": "testClientId", "destination_client_title": "تست اولیه عادی", "destination_user_type": "prop", "fa_destination_user_type": "سکوی معامله", "fa_source_user_type": "-", "reason": "دریافت اعتبار معاملاتی", "source_client_id": "1", "source_client_title": null, "source_user_type": "wallex-to-margin-insurance", "unique_id": 7923, "value": "200000000"}]`) |
| `result[].createdAt` | string |  |  (example: `"2025-04-06T11:54:31Z"`) |
| `result[].currency` | string |  |  (example: `"TMN"`) |
| `result[].destination_client_id` | string |  |  (example: `"3"`) |
| `result[].destination_client_title` | string |  |  |
| `result[].destination_user_type` | string |  |  (example: `"wallex-to-subrogation"`) |
| `result[].fa_destination_user_type` | string |  |  (example: `"والکس(به‌وکالت)"`) |
| `result[].fa_source_user_type` | string |  |  (example: `"سکوی معامله"`) |
| `result[].reason` | string |  |  (example: `"هزینه عملیات سکو"`) |
| `result[].source_client_id` | string |  |  (example: `"testClientId"`) |
| `result[].source_client_title` | string |  |  (example: `"تست اولیه عادی"`) |
| `result[].source_user_type` | string |  |  (example: `"prop"`) |
| `result[].unique_id` | number |  |  (example: `7924`) |
| `result[].value` | string |  |  (example: `"201000000"`) |
| `result_info` | object |  |  |
| `result_info.count` | number |  |  (example: `1`) |
| `result_info.page` | number |  |  (example: `1`) |
| `result_info.per_page` | number |  |  (example: `15`) |
| `result_info.total_count` | number |  |  (example: `3`) |
| `success` | boolean |  |  (example: `true`) |

<details><summary>Example / shape</summary>

```json
{
  "message": "عملیات با موفقیت انجام شد",
  "result": [
    {
      "createdAt": "2025-04-06T11:54:31Z",
      "currency": "TMN",
      "destination_client_id": "3",
      "destination_client_title": null,
      "destination_user_type": "wallex-to-subrogation",
      "fa_destination_user_type": "والکس(به‌وکالت)",
      "fa_source_user_type": "سکوی معامله",
      "reason": "هزینه عملیات سکو",
      "source_client_id": "testClientId",
      "source_client_title": "تست اولیه عادی",
      "source_user_type": "prop",
      "unique_id": 7924,
      "value": "201000000"
    },
    {
      "createdAt": "2025-04-06T11:54:04Z",
      "currency": "TMN",
      "destination_client_id": "testClientId",
      "destination_client_title": "تست اولیه عادی",
      "destination_user_type": "prop",
      "fa_destination_user_type": "سکوی معامله",
      "fa_source_user_type": "اصلی",
      "reason": "دارایی ورودی طرح سکو",
      "source_client_id": "testUserId",
      "source_client_title": null,
      "source_user_type": "master",
      "unique_id": 7922,
      "value": "1000000"
    },
    {
      "createdAt": "2025-04-06T11:54:04Z",
      "currency": "TMN",
      "destination_client_id": "testClientId",
      "destination_client_title": "تست اولیه عادی",
      "destination_user_type": "prop",
      "fa_destination_user_type": "سکوی معامله",
      "fa_source_user_type": "-",
      "reason": "دریافت اعتبار معاملاتی",
      "source_client_id": "1",
      "source_client_title": null,
      "source_user_type": "wallex-to-margin-insurance",
      "unique_id": 7923,
      "value": "200000000"
    }
  ],
  "result_info": {
    "count": 1,
    "page": 1,
    "per_page": 15,
    "total_count": 3
  },
  "success": true
}
```

</details>
