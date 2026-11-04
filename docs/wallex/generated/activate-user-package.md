<!-- source: https://developers.wallex.ir/docs/generated/activate-user-package -->

# Activate User Package

`POST /v1/prop/user/packages`

**Base URL:** `https://api.wallex.ir`

# POST /v1/prop/user/packages

This endpoint retrieves transfer details for sub-accounts.

## Headers

This request does not require any custom header.

## Request Body Parameters

- `prop_package_id` (string)


## Query Parameters

This request does not require any query parameters.

## Response

- `result` (object)

    - `userId` (string)

    - `title` (string)

    - `darkAvatarUrl` (string)

    - `lightAvatarUrl` (string)

    - `clientId` (string)

    - `isActive` (boolean)

    - `type` (string)

    - `createdAt` (string)

    - `isSuspend` (boolean)

- `message` (string)

- `success` (boolean)


## Example Response

``` json
{
    "result": {
        "userId": "0",
        "title": "تست اولیه عادی",
        "darkAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
        "lightAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
        "clientId": "CLIENTID",
        "isActive": true,
        "type": "prop",
        "createdAt": "2025-04-06T11:53:18Z",
        "isSuspend": false
    },
    "message": "عملیات با موفقیت انجام شد",
    "success": true
}

 ```

**Tags:** trade-credit

## Authentication

- `x-api-key` — apiKey in header `x-api-key`

## Request body

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `prop_package_id` | number |  |  (example: `69`) |

**Example:**

```json
{
  "prop_package_id": 69
}
```

## Responses

### 201 — 201

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `message` | string |  |  (example: `"عملیات با موفقیت انجام شد"`) |
| `result` | object |  |  |
| `result.clientId` | string |  |  (example: `"CLIENTID"`) |
| `result.createdAt` | string |  |  (example: `"2025-04-06T11:53:18Z"`) |
| `result.darkAvatarUrl` | string |  |  (example: `"https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg"`) |
| `result.isActive` | boolean |  |  (example: `true`) |
| `result.isSuspend` | boolean |  |  (example: `false`) |
| `result.lightAvatarUrl` | string |  |  (example: `"https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg"`) |
| `result.title` | string |  |  (example: `"تست اولیه عادی"`) |
| `result.type` | string |  |  (example: `"prop"`) |
| `result.userId` | string |  |  (example: `"0"`) |
| `success` | boolean |  |  (example: `true`) |

<details><summary>Example / shape</summary>

```json
{
  "message": "عملیات با موفقیت انجام شد",
  "result": {
    "clientId": "CLIENTID",
    "createdAt": "2025-04-06T11:53:18Z",
    "darkAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
    "isActive": true,
    "isSuspend": false,
    "lightAvatarUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
    "title": "تست اولیه عادی",
    "type": "prop",
    "userId": "0"
  },
  "success": true
}
```

</details>
