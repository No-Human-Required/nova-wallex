<!-- source: https://developers.wallex.ir/docs/generated/create-transfer-to-sub-account -->

# Create Transfer To Sub Account

`POST /sub-accounts/transfers`

**Base URL:** `https://api.wallex.ir`

# POST /sub-accounts/transfers

This endpoint Submits Transfer from master account to sub-account.

## Headers

This request does not require any custom header.

## Request Body Parameters

- `currency` (string)

- `value` (number)

- `subAccount_client_id` (string)


## Query Parameters

This request does not require any query parameters.

## Response

- `result` (array\[object\])

    - `userId` (number)

    - `title` (string)

    - `darkAvatarUrl` (string)

    - `lightAvatarUrl` (string)

    - `clientId` (string)

    - `isActive` (bool)

    - `type` (string)

    - `isSuspend` (bool)

    - `createdAt` (string)

- `message` (string)

- `success` (boolean)


## Example Response

200

``` json
{
    "result": {
        "userId": 0,
        "title": "تست اولویت",
        "darkAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
        "lightAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
        "clientId": "CLIENTID",
        "isActive": true,
        "type": "prop",
        "createdAt": "2024-09-08T13:35:27Z",
        "isSuspend": false
    },
    "message": "عملیات با موفقیت انجام شد",
    "success": true
}

 ```

## 422

``` json
{
    "result": {
        "currency": [
            "انتقال ارز BTC به این اکانت مجاز نمی باشد."
        ]
    },
    "message": "اطلاعات وارد شده اشتباه است",
    "success": false,
    "code": 422
}

 ```

**Tags:** trade-credit

## Authentication

- `x-api-key` — apiKey in header `x-api-key`

## Parameters

| Name | In | Type | Required | Description |
| --- | --- | --- | --- | --- |
| `sub-account-client-id` | header | string |  |  |

## Request body

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `currency` | string |  |  (example: `"TMN"`) |
| `subAccount_client_id` | string |  |  (example: `"{{subAccountClientId}}"`) |
| `value` | string |  |  (example: `"1000"`) |

**Example:**

```json
{
  "currency": "TMN",
  "subAccount_client_id": "{{subAccountClientId}}",
  "value": "1000"
}
```

## Responses

### 200 — 200

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `message` | string |  |  (example: `"عملیات با موفقیت انجام شد"`) |
| `result` | object |  |  |
| `result.clientId` | string |  |  (example: `"CLIENTID"`) |
| `result.createdAt` | string |  |  (example: `"2024-09-08T13:35:27Z"`) |
| `result.darkAvatarUrl` | string |  |  (example: `"https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg"`) |
| `result.isActive` | boolean |  |  (example: `true`) |
| `result.isSuspend` | boolean |  |  (example: `false`) |
| `result.lightAvatarUrl` | string |  |  (example: `"https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg"`) |
| `result.title` | string |  |  (example: `"تست اولویت"`) |
| `result.type` | string |  |  (example: `"prop"`) |
| `result.userId` | number |  |  (example: `0`) |
| `success` | boolean |  |  (example: `true`) |

<details><summary>Example / shape</summary>

```json
{
  "message": "عملیات با موفقیت انجام شد",
  "result": {
    "clientId": "CLIENTID",
    "createdAt": "2024-09-08T13:35:27Z",
    "darkAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
    "isActive": true,
    "isSuspend": false,
    "lightAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
    "title": "تست اولویت",
    "type": "prop",
    "userId": 0
  },
  "success": true
}
```

</details>

### 422 — 422

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `code` | number |  |  (example: `422`) |
| `message` | string |  |  (example: `"اطلاعات وارد شده اشتباه است"`) |
| `result` | object |  |  |
| `result.currency` | array<string> |  |  (example: `["انتقال ارز BTC به این اکانت مجاز نمی باشد."]`) |
| `success` | boolean |  |  (example: `false`) |

<details><summary>Example / shape</summary>

```json
{
  "code": 422,
  "message": "اطلاعات وارد شده اشتباه است",
  "result": {
    "currency": [
      "انتقال ارز BTC به این اکانت مجاز نمی باشد."
    ]
  },
  "success": false
}
```

</details>
