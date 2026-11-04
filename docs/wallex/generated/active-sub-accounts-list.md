<!-- source: https://developers.wallex.ir/docs/generated/active-sub-accounts-list -->

# Active Sub Accounts List

`GET /sub-accounts`

**Base URL:** `https://api.wallex.ir`

# GET /sub-accounts

This endpoint retrieves the list of active sub-accounts.

## Headers

This request does not require any custom header.

## Request Body Parameters

This request does not require a request body.

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
            "userId": 0,
            "title": "تست اولیه عادی",
            "darkAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
            "lightAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
            "clientId": "CLIENTID",
            "isActive": true,
            "type": "prop",
            "createdAt": "2025-04-06T11:53:18Z",
            "isSuspend": false
        },
        {
            "userId": 0,
            "title": null,
            "darkAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
            "lightAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
            "clientId": "CLIENTID",
            "isActive": true,
            "type": "trading_bot_trade",
            "createdAt": "2024-11-19T09:20:37Z",
            "isSuspend": false
        }
    ],
    "message": "عملیات با موفقیت انجام شد",
    "success": true,
    "result_info": {
        "page": 1,
        "per_page": 11,
        "count": 11,
        "total_count": 11
    }
}

 ```

**Tags:** trade-credit

## Authentication

- `x-api-key` — apiKey in header `x-api-key`

## Responses

### 200 — 200

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `message` | string |  |  (example: `"عملیات با موفقیت انجام شد"`) |
| `result` | array<object> |  |  (example: `[{"clientId": "CLIENTID", "createdAt": "2025-04-06T11:53:18Z", "darkAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg", "isActive": true, "isSuspend": false, "lightAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg", "title": "تست اولیه عادی", "type": "prop", "userId": 0}, {"clientId": "CLIENTID", "createdAt": "2024-11-19T09:20:37Z", "darkAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg", "isActive": true, "isSuspend": false, "lightAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg", "title": null, "type": "trading_bot_trade", "userId": 0}, {"clientId": "CLIENTID", "createdAt": "2024-11-19T11:55:57Z", "darkAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg", "isActive": true, "isSuspend": false, "lightAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg", "title": null, "type": "trading_bot_trade", "userId": 0}, {"clientId": "CLIENTID", "createdAt": "2024-11-23T09:09:41Z", "darkAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg", "isActive": true, "isSuspend": false, "lightAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg", "title": null, "type": "trading_bot_trade", "userId": 0}, {"clientId": "CLIENTID", "createdAt": "2024-11-23T09:13:57Z", "darkAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg", "isActive": true, "isSuspend": false, "lightAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg", "title": null, "type": "trading_bot_trade", "userId": 0}, {"clientId": "CLIENTID", "createdAt": "2024-11-25T07:56:11Z", "darkAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg", "isActive": true, "isSuspend": false, "lightAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg", "title": null, "type": "trading_bot_trade", "userId": 0}, {"clientId": "CLIENTID", "createdAt": "2024-12-05T10:18:42Z", "darkAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg", "isActive": true, "isSuspend": false, "lightAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg", "title": null, "type": "trading_bot_trade", "userId": 0}, {"clientId": "CLIENTID", "createdAt": "2024-12-05T10:20:59Z", "darkAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg", "isActive": true, "isSuspend": false, "lightAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg", "title": null, "type": "trading_bot_trade", "userId": 0}, {"clientId": "CLIENTID", "createdAt": "2024-12-05T10:21:45Z", "darkAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg", "isActive": true, "isSuspend": false, "lightAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg", "title": null, "type": "trading_bot_trade", "userId": 0}, {"clientId": "CLIENTID", "createdAt": "2024-12-05T10:56:16Z", "darkAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg", "isActive": true, "isSuspend": false, "lightAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg", "title": null, "type": "trading_bot_trade", "userId": 0}, {"clientId": "CLIENTID", "createdAt": "2025-02-01T12:24:51Z", "darkAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg", "isActive": true, "isSuspend": false, "lightAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg", "title": null, "type": "trading_bot_trade", "userId": 0}]`) |
| `result[].clientId` | string |  |  (example: `"ClientID"`) |
| `result[].createdAt` | string |  |  (example: `"2025-04-06T11:53:18Z"`) |
| `result[].darkAvatarUrl` | string |  |  (example: `"https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg"`) |
| `result[].isActive` | boolean |  |  (example: `true`) |
| `result[].isSuspend` | boolean |  |  (example: `false`) |
| `result[].lightAvatarUrl` | string |  |  (example: `"https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg"`) |
| `result[].title` | string |  |  (example: `"تست اولیه عادی"`) |
| `result[].type` | string |  |  (example: `"prop"`) |
| `result[].userId` | number |  |  (example: `0`) |
| `result_info` | object |  |  |
| `result_info.count` | number |  |  (example: `11`) |
| `result_info.page` | number |  |  (example: `1`) |
| `result_info.per_page` | number |  |  (example: `11`) |
| `result_info.total_count` | number |  |  (example: `11`) |
| `success` | boolean |  |  (example: `true`) |

<details><summary>Example / shape</summary>

```json
{
  "message": "عملیات با موفقیت انجام شد",
  "result": [
    {
      "clientId": "CLIENTID",
      "createdAt": "2025-04-06T11:53:18Z",
      "darkAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
      "isActive": true,
      "isSuspend": false,
      "lightAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
      "title": "تست اولیه عادی",
      "type": "prop",
      "userId": 0
    },
    {
      "clientId": "CLIENTID",
      "createdAt": "2024-11-19T09:20:37Z",
      "darkAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
      "isActive": true,
      "isSuspend": false,
      "lightAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
      "title": null,
      "type": "trading_bot_trade",
      "userId": 0
    },
    {
      "clientId": "CLIENTID",
      "createdAt": "2024-11-19T11:55:57Z",
      "darkAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
      "isActive": true,
      "isSuspend": false,
      "lightAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
      "title": null,
      "type": "trading_bot_trade",
      "userId": 0
    },
    {
      "clientId": "CLIENTID",
      "createdAt": "2024-11-23T09:09:41Z",
      "darkAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
      "isActive": true,
      "isSuspend": false,
      "lightAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
      "title": null,
      "type": "trading_bot_trade",
      "userId": 0
    },
    {
      "clientId": "CLIENTID",
      "createdAt": "2024-11-23T09:13:57Z",
      "darkAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
      "isActive": true,
      "isSuspend": false,
      "lightAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
      "title": null,
      "type": "trading_bot_trade",
      "userId": 0
    },
    {
      "clientId": "CLIENTID",
      "createdAt": "2024-11-25T07:56:11Z",
      "darkAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
      "isActive": true,
      "isSuspend": false,
      "lightAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
      "title": null,
      "type": "trading_bot_trade",
      "userId": 0
    },
    {
      "clientId": "CLIENTID",
      "createdAt": "2024-12-05T10:18:42Z",
      "darkAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
      "isActive": true,
      "isSuspend": false,
      "lightAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
      "title": null,
      "type": "trading_bot_trade",
      "userId": 0
    },
    {
      "clientId": "CLIENTID",
      "createdAt": "2024-12-05T10:20:59Z",
      "darkAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
      "isActive": true,
      "isSuspend": false,
      "lightAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
      "title": null,
      "type": "trading_bot_trade",
      "userId": 0
    },
    {
      "clientId": "CLIENTID",
      "createdAt": "2024-12-05T10:21:45Z",
      "darkAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
      "isActive": true,
      "isSuspend": false,
      "lightAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
      "title": null,
      "type": "trading_bot_trade",
      "userId": 0
    },
    {
      "clientId": "CLIENTID",
      "createdAt": "2024-12-05T10:56:16Z",
      "darkAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
      "isActive": true,
      "isSuspend": false,
      "lightAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
      "title": null,
      "type": "trading_bot_trade",
      "userId": 0
    },
    {
      "clientId": "CLIENTID",
      "createdAt": "2025-02-01T12:24:51Z",
      "darkAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
      "isActive": true,
      "isSuspend": false,
      "lightAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
      "title": null,
      "type": "trading_bot_trade",
      "userId": 0
    }
  ],
  "result_info": {
    "count": 11,
    "page": 1,
    "per_page": 11,
    "total_count": 11
  },
  "success": true
}
```

</details>
