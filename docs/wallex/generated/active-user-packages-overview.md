<!-- source: https://developers.wallex.ir/docs/generated/active-user-packages-overview -->

# Active User Packages Overview

`GET /v1/prop/user/packages/overview`

**Base URL:** `https://api.wallex.ir`

# GET /v1/prop/user/packages/overview

This endpoint retrieves an overview of active user packages

## Headers

This request does not require any custom header.

## Request Body Parameters

This request does not require a request body.

## Query Parameters

This request does not require any query parameters.

## Response

- `result` (object)

    - `aggregatedDetail` (object)

        - `currency` (string)

        - `assurance` (string)

        - `loan` (string)

        - `profit` (string)

        - `profitPercentage` (string)

    - `userPackages` (array\[object\])

        - `packageDetail` (object)

            - `title` (string)

            - `assurance` (string)

            - `loan` (string)

            - `currency` (string)

            - `darkImageUrl` (string)

            - `lightImageUrl` (string)

            - `expireDays` (number)

    - `userPackageDetail` (object)

        - `id` (number)

        - `subAccountClientId` (string)

        - `status` (string)

        - `createdAt` (string)

        - `expireAt` (string)

        - `profit` (string)

        - `profitPercentage` (string)

    - `balancesHistory` (object)

        - `total` (object)

            - `TMN` (number)

            - `USDT` (number)

            - `BTC` (number)

        - `perDay` (object)

            - (object)

                - `TMN` (number)

                - `USDT` (number)

                - `BTC` (number)

- `message` (string)

- `success` (boolean)


## Example Response

``` json
{
    "result": {
        "aggregatedDetail": {
            "currency": "TMN",
            "assurance": "1000000",
            "loan": "200000000",
            "profit": "-1999995000",
            "profitPercentage": "-995.02"
        },
        "userPackages": [
            {
                "packageDetail": {
                    "title": "طرح ۵",
                    "assurance": "1000000",
                    "loan": "200000000",
                    "currency": "TMN",
                    "darkImageUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
                    "lightImageUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
                    "expireDays": 30
                },
                "userPackageDetail": {
                    "id": 339,
                    "subAccountClientId": "CLIENTID",
                    "status": "liquid",
                    "createdAt": "2025-04-06T11:50:11.000000Z",
                    "expireAt": "2025-05-06T11:50:11.000000Z",
                    "profit": "-1999995000",
                    "profitPercentage": "-995.02"
                },
                "balancesHistory": {
                    "total": {
                        "TMN": 201000000,
                        "USDT": 1939.087567651003,
                        "BTC": 0.023551144650712032
                    },
                    "perDay": {
                        "2025-04-06": {
                            "TMN": 201000000,
                            "USDT": 1939.087567651003,
                            "BTC": 0.023551144650712032
                        }
                    }
                }
            }
        ]
    },
    "message": "عملیات با موفقیت انجام شد",
    "success": true
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
| `result` | object |  |  |
| `result.aggregatedDetail` | object |  |  |
| `result.aggregatedDetail.assurance` | string |  |  (example: `"1000000"`) |
| `result.aggregatedDetail.currency` | string |  |  (example: `"TMN"`) |
| `result.aggregatedDetail.loan` | string |  |  (example: `"200000000"`) |
| `result.aggregatedDetail.profit` | string |  |  (example: `"-1999995000"`) |
| `result.aggregatedDetail.profitPercentage` | string |  |  (example: `"-995.02"`) |
| `result.userPackages` | array<object> |  |  (example: `[{"balancesHistory": {"perDay": {"2025-04-06": {"BTC": 0.023551144650712032, "TMN": 201000000, "USDT": 1939.087567651003}}, "total": {"BTC": 0.023551144650712032, "TMN": 201000000, "USDT": 1939.087567651003}}, "packageDetail": {"assurance": "1000000", "currency": "TMN", "darkImageUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg", "expireDays": 30, "lightImageUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg", "loan": "200000000", "title": "طرح ۵"}, "userPackageDetail": {"createdAt": "2025-04-06T11:50:11.000000Z", "expireAt": "2025-05-06T11:50:11.000000Z", "id": 339, "profit": "-1999995000", "profitPercentage": "-995.02", "status": "liquid", "subAccountClientId": "CLIENTID"}}]`) |
| `result.userPackages[].balancesHistory` | object |  |  |
| `result.userPackages[].balancesHistory.perDay` | object |  |  |
| `result.userPackages[].balancesHistory.perDay.2025-04-06` | object |  |  |
| `result.userPackages[].balancesHistory.perDay.2025-04-06.BTC` | number |  |  (example: `0.023551144650712032`) |
| `result.userPackages[].balancesHistory.perDay.2025-04-06.TMN` | number |  |  (example: `201000000`) |
| `result.userPackages[].balancesHistory.perDay.2025-04-06.USDT` | number |  |  (example: `1939.087567651003`) |
| `result.userPackages[].balancesHistory.total` | object |  |  |
| `result.userPackages[].balancesHistory.total.BTC` | number |  |  (example: `0.023551144650712032`) |
| `result.userPackages[].balancesHistory.total.TMN` | number |  |  (example: `201000000`) |
| `result.userPackages[].balancesHistory.total.USDT` | number |  |  (example: `1939.087567651003`) |
| `result.userPackages[].packageDetail` | object |  |  |
| `result.userPackages[].packageDetail.assurance` | string |  |  (example: `"1000000"`) |
| `result.userPackages[].packageDetail.currency` | string |  |  (example: `"TMN"`) |
| `result.userPackages[].packageDetail.darkImageUrl` | string |  |  (example: `"https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg"`) |
| `result.userPackages[].packageDetail.expireDays` | number |  |  (example: `30`) |
| `result.userPackages[].packageDetail.lightImageUrl` | string |  |  (example: `"https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg"`) |
| `result.userPackages[].packageDetail.loan` | string |  |  (example: `"200000000"`) |
| `result.userPackages[].packageDetail.title` | string |  |  (example: `"طرح ۵"`) |
| `result.userPackages[].userPackageDetail` | object |  |  |
| `result.userPackages[].userPackageDetail.createdAt` | string |  |  (example: `"2025-04-06T11:50:11.000000Z"`) |
| `result.userPackages[].userPackageDetail.expireAt` | string |  |  (example: `"2025-05-06T11:50:11.000000Z"`) |
| `result.userPackages[].userPackageDetail.id` | number |  |  (example: `339`) |
| `result.userPackages[].userPackageDetail.profit` | string |  |  (example: `"-1999995000"`) |
| `result.userPackages[].userPackageDetail.profitPercentage` | string |  |  (example: `"-995.02"`) |
| `result.userPackages[].userPackageDetail.status` | string |  |  (example: `"liquid"`) |
| `result.userPackages[].userPackageDetail.subAccountClientId` | string |  |  (example: `"CLIENTID"`) |
| `success` | boolean |  |  (example: `true`) |

<details><summary>Example / shape</summary>

```json
{
  "message": "عملیات با موفقیت انجام شد",
  "result": {
    "aggregatedDetail": {
      "assurance": "1000000",
      "currency": "TMN",
      "loan": "200000000",
      "profit": "-1999995000",
      "profitPercentage": "-995.02"
    },
    "userPackages": [
      {
        "balancesHistory": {
          "perDay": {
            "2025-04-06": {
              "BTC": 0.023551144650712032,
              "TMN": 201000000,
              "USDT": 1939.087567651003
            }
          },
          "total": {
            "BTC": 0.023551144650712032,
            "TMN": 201000000,
            "USDT": 1939.087567651003
          }
        },
        "packageDetail": {
          "assurance": "1000000",
          "currency": "TMN",
          "darkImageUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
          "expireDays": 30,
          "lightImageUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
          "loan": "200000000",
          "title": "طرح ۵"
        },
        "userPackageDetail": {
          "createdAt": "2025-04-06T11:50:11.000000Z",
          "expireAt": "2025-05-06T11:50:11.000000Z",
          "id": 339,
          "profit": "-1999995000",
          "profitPercentage": "-995.02",
          "status": "liquid",
          "subAccountClientId": "CLIENTID"
        }
      }
    ]
  },
  "success": true
}
```

</details>
