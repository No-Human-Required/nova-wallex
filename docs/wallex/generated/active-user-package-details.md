<!-- source: https://developers.wallex.ir/docs/generated/active-user-package-details -->

# Active User Package Details

`GET /v1/prop/user/packages/active`

**Base URL:** `https://api.wallex.ir`

# GET /v1/prop/user/packages/active

This endpoint retrieves the details of a user package based on sub account.

## Headers

- `Sub-Account-Client-id` (string)

## Request Body Parameters

This request does not require a request body.

## Query Parameters

This request does not require any query parameters.

## Response

- `result` (object)

    - `packageDetail` (object)

        - `id` (number)

        - `title` (string)

        - `assurance` (string)

        - `loan` (string)

        - `currency` (string)

        - `destination_currency` (null|string)

        - `dailyFee` (string)

        - `dailyFeeDiscount` (string)

        - `dailyFeeAfterDiscount` (string)

        - `darkImageUrl` (string)

        - `lightImageUrl` (string)

        - `startBalance` (string)

        - `expireDays` (number)

    - `userPackageDetail` (object)

        - `id` (number)

        - `status` (string)

        - `createdAt` (string)

        - `expireAt` (string)

        - `type` (string)

        - `openDays` (number)

        - `totalDays` (number)

        - `cyclesCount` (number)

        - `debtCyclesCount` (number)

        - `paidCyclesCount` (number)

        - `warningLimit` (string)

        - `liquidityLimit` (string)

        - `profit` (string)

        - `profitPercentage` (string)

        - `connectToWallet` (null|string)

        - `finalFeeAfterDiscount` (string)

        - `finalFee` (string)

        - `finalPayableFeeAmount` (string)

        - `finalPayback` (string)

    - `alertsData` (array\[object\])

        - `type` (string)

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
        "packageDetail": {
            "id": 69,
            "title": "طرح ۵",
            "assurance": "1000000",
            "loan": "200000000",
            "currency": "TMN",
            "destination_currency": null,
            "dailyFee": "2000000000",
            "dailyFeeDiscount": "5000",
            "dailyFeeAfterDiscount": "1999995000",
            "darkImageUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
            "lightImageUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
            "startBalance": "201000000",
            "expireDays": 30
        },
        "userPackageDetail": {
            "id": 339,
            "status": "liquid",
            "createdAt": "2025-04-06T11:50:11.000000Z",
            "expireAt": "2025-05-06T11:50:11.000000Z",
            "type": "prop-public",
            "openDays": 1,
            "totalDays": 1,
            "cyclesCount": 1,
            "debtCyclesCount": 1,
            "paidCyclesCount": 0,
            "warningLimit": "2200795000",
            "liquidityLimit": "2200495000",
            "profit": "-1999995000",
            "profitPercentage": "-995.02",
            "connectToWallet": null,
            "finalFeeAfterDiscount": "59999850000",
            "finalFee": "60000000000",
            "finalPayableFeeAmount": "1999995000",
            "finalPayback": "2199995000"
        },
        "alertsData": [
            {
                "type": "public_warning_low_credit"
            }
        ],
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
| `sub-account-client-id` | header | string |  |  |

## Responses

### 200 — 200

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `message` | string |  |  (example: `"عملیات با موفقیت انجام شد"`) |
| `result` | object |  |  |
| `result.alertsData` | array<object> |  |  (example: `[{"type": "public_warning_low_credit"}]`) |
| `result.alertsData[].type` | string |  |  (example: `"public_warning_low_credit"`) |
| `result.balancesHistory` | object |  |  |
| `result.balancesHistory.perDay` | object |  |  |
| `result.balancesHistory.perDay.2025-04-06` | object |  |  |
| `result.balancesHistory.perDay.2025-04-06.BTC` | number |  |  (example: `0.023551144650712032`) |
| `result.balancesHistory.perDay.2025-04-06.TMN` | number |  |  (example: `201000000`) |
| `result.balancesHistory.perDay.2025-04-06.USDT` | number |  |  (example: `1939.087567651003`) |
| `result.balancesHistory.total` | object |  |  |
| `result.balancesHistory.total.BTC` | number |  |  (example: `0.023551144650712032`) |
| `result.balancesHistory.total.TMN` | number |  |  (example: `201000000`) |
| `result.balancesHistory.total.USDT` | number |  |  (example: `1939.087567651003`) |
| `result.packageDetail` | object |  |  |
| `result.packageDetail.assurance` | string |  |  (example: `"1000000"`) |
| `result.packageDetail.currency` | string |  |  (example: `"TMN"`) |
| `result.packageDetail.dailyFee` | string |  |  (example: `"2000000000"`) |
| `result.packageDetail.dailyFeeAfterDiscount` | string |  |  (example: `"1999995000"`) |
| `result.packageDetail.dailyFeeDiscount` | string |  |  (example: `"5000"`) |
| `result.packageDetail.darkImageUrl` | string |  |  (example: `"https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg"`) |
| `result.packageDetail.destination_currency` | any |  |  |
| `result.packageDetail.expireDays` | number |  |  (example: `30`) |
| `result.packageDetail.id` | number |  |  (example: `69`) |
| `result.packageDetail.lightImageUrl` | string |  |  (example: `"https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg"`) |
| `result.packageDetail.loan` | string |  |  (example: `"200000000"`) |
| `result.packageDetail.startBalance` | string |  |  (example: `"201000000"`) |
| `result.packageDetail.title` | string |  |  (example: `"طرح ۵"`) |
| `result.userPackageDetail` | object |  |  |
| `result.userPackageDetail.connectToWallet` | any |  |  |
| `result.userPackageDetail.createdAt` | string |  |  (example: `"2025-04-06T11:50:11.000000Z"`) |
| `result.userPackageDetail.cyclesCount` | number |  |  (example: `1`) |
| `result.userPackageDetail.debtCyclesCount` | number |  |  (example: `1`) |
| `result.userPackageDetail.expireAt` | string |  |  (example: `"2025-05-06T11:50:11.000000Z"`) |
| `result.userPackageDetail.finalFee` | string |  |  (example: `"60000000000"`) |
| `result.userPackageDetail.finalFeeAfterDiscount` | string |  |  (example: `"59999850000"`) |
| `result.userPackageDetail.finalPayableFeeAmount` | string |  |  (example: `"1999995000"`) |
| `result.userPackageDetail.finalPayback` | string |  |  (example: `"2199995000"`) |
| `result.userPackageDetail.id` | number |  |  (example: `339`) |
| `result.userPackageDetail.liquidityLimit` | string |  |  (example: `"2200495000"`) |
| `result.userPackageDetail.openDays` | number |  |  (example: `1`) |
| `result.userPackageDetail.paidCyclesCount` | number |  |  (example: `0`) |
| `result.userPackageDetail.profit` | string |  |  (example: `"-1999995000"`) |
| `result.userPackageDetail.profitPercentage` | string |  |  (example: `"-995.02"`) |
| `result.userPackageDetail.status` | string |  |  (example: `"liquid"`) |
| `result.userPackageDetail.totalDays` | number |  |  (example: `1`) |
| `result.userPackageDetail.type` | string |  |  (example: `"prop-public"`) |
| `result.userPackageDetail.warningLimit` | string |  |  (example: `"2200795000"`) |
| `success` | boolean |  |  (example: `true`) |

<details><summary>Example / shape</summary>

```json
{
  "message": "عملیات با موفقیت انجام شد",
  "result": {
    "alertsData": [
      {
        "type": "public_warning_low_credit"
      }
    ],
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
      "dailyFee": "2000000000",
      "dailyFeeAfterDiscount": "1999995000",
      "dailyFeeDiscount": "5000",
      "darkImageUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
      "destination_currency": null,
      "expireDays": 30,
      "id": 69,
      "lightImageUrl": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
      "loan": "200000000",
      "startBalance": "201000000",
      "title": "طرح ۵"
    },
    "userPackageDetail": {
      "connectToWallet": null,
      "createdAt": "2025-04-06T11:50:11.000000Z",
      "cyclesCount": 1,
      "debtCyclesCount": 1,
      "expireAt": "2025-05-06T11:50:11.000000Z",
      "finalFee": "60000000000",
      "finalFeeAfterDiscount": "59999850000",
      "finalPayableFeeAmount": "1999995000",
      "finalPayback": "2199995000",
      "id": 339,
      "liquidityLimit": "2200495000",
      "openDays": 1,
      "paidCyclesCount": 0,
      "profit": "-1999995000",
      "profitPercentage": "-995.02",
      "status": "liquid",
      "totalDays": 1,
      "type": "prop-public",
      "warningLimit": "2200795000"
    }
  },
  "success": true
}
```

</details>
