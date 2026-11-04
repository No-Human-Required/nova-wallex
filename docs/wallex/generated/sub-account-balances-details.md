<!-- source: https://developers.wallex.ir/docs/generated/sub-account-balances-details -->

# Sub Account Balances Details

`GET /v1/account/balances-detail`

**Base URL:** `https://api.wallex.ir`

# GET /v1/account/balances-detail

This endpoint retrieves the detailed balance information for the account.

## Headers

This request does not require any custom header.

## Request Body Parameters

This request does not require a request body.

## Query Parameters

This request does not require any query parameters.

## Response

- `result` (object)

    - `CURRENCY` (object) // balance currency symbol

        - `symbol` (string)

        - `total` (string)

        - `freeze` (string)

        - `available` (string)

        - `stats` (object)

            - `BTC` (object)

                - `baseMarketName` (string)

                - `changePercentage` (string)

                - `estimatedValue` (string)

                - `last24HoursEstimatedValueChange` (string)

            - `USDT` (object)

                - `baseMarketName` (string)

                - `changePercentage` (string)

                - `estimatedValue` (string)

                - `last24HoursEstimatedValueChange` (string)

            - `TMN` (object)

                - `changePercentage` (string)

                - `estimatedValue` (string)

                - `last24HoursEstimatedValueChange` (string)

- `message` (string)
- `success` (boolean)

## Example Response

``` json
{
    "result": {
        "TMN": {
            "symbol": "TMN",
            "total": "0",
            "freeze": "0",
            "available": "0",
            "stats": {
                "BTC": {
                    "baseMarketName": "BTC",
                    "changePercentage": "7.69",
                    "estimatedValue": "0.00",
                    "last24HoursEstimatedValueChange": "0.00"
                },
                "USDT": {
                    "baseMarketName": "USDT",
                    "changePercentage": "-1.00",
                    "estimatedValue": "0.00",
                    "last24HoursEstimatedValueChange": "0.00"
                },
                "TMN": {
                    "changePercentage": "0.00",
                    "estimatedValue": "0",
                    "last24HoursEstimatedValueChange": "0"
                }
            }
        },
        "USDT": {
            // similar to TMN
        },
        "BTC": {
            // similar to BTC
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
| `result.BTC` | object |  |  |
| `result.BTC.available` | string |  |  (example: `"0"`) |
| `result.BTC.freeze` | string |  |  (example: `"0"`) |
| `result.BTC.stats` | object |  |  |
| `result.BTC.stats.BTC` | object |  |  |
| `result.BTC.stats.BTC.changePercentage` | string |  |  (example: `"0.00"`) |
| `result.BTC.stats.BTC.estimatedValue` | string |  |  (example: `"0.00"`) |
| `result.BTC.stats.BTC.last24HoursEstimatedValueChange` | string |  |  (example: `"0.00"`) |
| `result.BTC.stats.TMN` | object |  |  |
| `result.BTC.stats.TMN.baseMarketName` | string |  |  (example: `"TMN"`) |
| `result.BTC.stats.TMN.changePercentage` | string |  |  (example: `"7.69"`) |
| `result.BTC.stats.TMN.estimatedValue` | string |  |  (example: `"0"`) |
| `result.BTC.stats.TMN.last24HoursEstimatedValueChange` | string |  |  (example: `"0"`) |
| `result.BTC.stats.USDT` | object |  |  |
| `result.BTC.stats.USDT.baseMarketName` | string |  |  (example: `"USDT"`) |
| `result.BTC.stats.USDT.changePercentage` | string |  |  (example: `"8.42"`) |
| `result.BTC.stats.USDT.estimatedValue` | string |  |  (example: `"0.00"`) |
| `result.BTC.stats.USDT.last24HoursEstimatedValueChange` | string |  |  (example: `"0.00"`) |
| `result.BTC.symbol` | string |  |  (example: `"BTC"`) |
| `result.BTC.total` | string |  |  (example: `"0"`) |
| `result.ETH` | object |  |  |
| `result.ETH.available` | string |  |  (example: `"0"`) |
| `result.ETH.freeze` | string |  |  (example: `"0"`) |
| `result.ETH.stats` | object |  |  |
| `result.ETH.stats.BTC` | object |  |  |
| `result.ETH.stats.BTC.changePercentage` | string |  |  (example: `"0.00"`) |
| `result.ETH.stats.BTC.estimatedValue` | string |  |  (example: `"0.00"`) |
| `result.ETH.stats.BTC.last24HoursEstimatedValueChange` | string |  |  (example: `"0.00"`) |
| `result.ETH.stats.TMN` | object |  |  |
| `result.ETH.stats.TMN.baseMarketName` | string |  |  (example: `"TMN"`) |
| `result.ETH.stats.TMN.changePercentage` | string |  |  (example: `"4.43"`) |
| `result.ETH.stats.TMN.estimatedValue` | string |  |  (example: `"0"`) |
| `result.ETH.stats.TMN.last24HoursEstimatedValueChange` | string |  |  (example: `"0"`) |
| `result.ETH.stats.USDT` | object |  |  |
| `result.ETH.stats.USDT.baseMarketName` | string |  |  (example: `"USDT"`) |
| `result.ETH.stats.USDT.changePercentage` | string |  |  (example: `"6.11"`) |
| `result.ETH.stats.USDT.estimatedValue` | string |  |  (example: `"0.00"`) |
| `result.ETH.stats.USDT.last24HoursEstimatedValueChange` | string |  |  (example: `"0.00"`) |
| `result.ETH.symbol` | string |  |  (example: `"ETH"`) |
| `result.ETH.total` | string |  |  (example: `"0"`) |
| `result.TMN` | object |  |  |
| `result.TMN.available` | string |  |  (example: `"0"`) |
| `result.TMN.freeze` | string |  |  (example: `"0"`) |
| `result.TMN.stats` | object |  |  |
| `result.TMN.stats.BTC` | object |  |  |
| `result.TMN.stats.BTC.baseMarketName` | string |  |  (example: `"BTC"`) |
| `result.TMN.stats.BTC.changePercentage` | string |  |  (example: `"7.69"`) |
| `result.TMN.stats.BTC.estimatedValue` | string |  |  (example: `"0.00"`) |
| `result.TMN.stats.BTC.last24HoursEstimatedValueChange` | string |  |  (example: `"0.00"`) |
| `result.TMN.stats.TMN` | object |  |  |
| `result.TMN.stats.TMN.changePercentage` | string |  |  (example: `"0.00"`) |
| `result.TMN.stats.TMN.estimatedValue` | string |  |  (example: `"0"`) |
| `result.TMN.stats.TMN.last24HoursEstimatedValueChange` | string |  |  (example: `"0"`) |
| `result.TMN.stats.USDT` | object |  |  |
| `result.TMN.stats.USDT.baseMarketName` | string |  |  (example: `"USDT"`) |
| `result.TMN.stats.USDT.changePercentage` | string |  |  (example: `"-1.00"`) |
| `result.TMN.stats.USDT.estimatedValue` | string |  |  (example: `"0.00"`) |
| `result.TMN.stats.USDT.last24HoursEstimatedValueChange` | string |  |  (example: `"0.00"`) |
| `result.TMN.symbol` | string |  |  (example: `"TMN"`) |
| `result.TMN.total` | string |  |  (example: `"0"`) |
| `result.USDT` | object |  |  |
| `result.USDT.available` | string |  |  (example: `"0"`) |
| `result.USDT.freeze` | string |  |  (example: `"0"`) |
| `result.USDT.stats` | object |  |  |
| `result.USDT.stats.BTC` | object |  |  |
| `result.USDT.stats.BTC.baseMarketName` | string |  |  (example: `"BTC"`) |
| `result.USDT.stats.BTC.changePercentage` | string |  |  (example: `"8.42"`) |
| `result.USDT.stats.BTC.estimatedValue` | string |  |  (example: `"0.00"`) |
| `result.USDT.stats.BTC.last24HoursEstimatedValueChange` | string |  |  (example: `"0.00"`) |
| `result.USDT.stats.TMN` | object |  |  |
| `result.USDT.stats.TMN.baseMarketName` | string |  |  (example: `"TMN"`) |
| `result.USDT.stats.TMN.changePercentage` | string |  |  (example: `"-1.00"`) |
| `result.USDT.stats.TMN.estimatedValue` | string |  |  (example: `"0"`) |
| `result.USDT.stats.TMN.last24HoursEstimatedValueChange` | string |  |  (example: `"0"`) |
| `result.USDT.stats.USDT` | object |  |  |
| `result.USDT.stats.USDT.changePercentage` | string |  |  (example: `"0.00"`) |
| `result.USDT.stats.USDT.estimatedValue` | string |  |  (example: `"0.00"`) |
| `result.USDT.stats.USDT.last24HoursEstimatedValueChange` | string |  |  (example: `"0.00"`) |
| `result.USDT.symbol` | string |  |  (example: `"USDT"`) |
| `result.USDT.total` | string |  |  (example: `"0"`) |
| `success` | boolean |  |  (example: `true`) |

<details><summary>Example / shape</summary>

```json
{
  "message": "عملیات با موفقیت انجام شد",
  "result": {
    "BTC": {
      "available": "0",
      "freeze": "0",
      "stats": {
        "BTC": {
          "changePercentage": "0.00",
          "estimatedValue": "0.00",
          "last24HoursEstimatedValueChange": "0.00"
        },
        "TMN": {
          "baseMarketName": "TMN",
          "changePercentage": "7.69",
          "estimatedValue": "0",
          "last24HoursEstimatedValueChange": "0"
        },
        "USDT": {
          "baseMarketName": "USDT",
          "changePercentage": "8.42",
          "estimatedValue": "0.00",
          "last24HoursEstimatedValueChange": "0.00"
        }
      },
      "symbol": "BTC",
      "total": "0"
    },
    "ETH": {
      "available": "0",
      "freeze": "0",
      "stats": {
        "BTC": {
          "changePercentage": "0.00",
          "estimatedValue": "0.00",
          "last24HoursEstimatedValueChange": "0.00"
        },
        "TMN": {
          "baseMarketName": "TMN",
          "changePercentage": "4.43",
          "estimatedValue": "0",
          "last24HoursEstimatedValueChange": "0"
        },
        "USDT": {
          "baseMarketName": "USDT",
          "changePercentage": "6.11",
          "estimatedValue": "0.00",
          "last24HoursEstimatedValueChange": "0.00"
        }
      },
      "symbol": "ETH",
      "total": "0"
    },
    "TMN": {
      "available": "0",
      "freeze": "0",
      "stats": {
        "BTC": {
          "baseMarketName": "BTC",
          "changePercentage": "7.69",
          "estimatedValue": "0.00",
          "last24HoursEstimatedValueChange": "0.00"
        },
        "TMN": {
          "changePercentage": "0.00",
          "estimatedValue": "0",
          "last24HoursEstimatedValueChange": "0"
        },
        "USDT": {
          "baseMarketName": "USDT",
          "changePercentage": "-1.00",
          "estimatedValue": "0.00",
          "last24HoursEstimatedValueChange": "0.00"
        }
      },
      "symbol": "TMN",
      "total": "0"
    },
    "USDT": {
      "available": "0",
      "freeze": "0",
      "stats": {
        "BTC": {
          "baseMarketName": "BTC",
          "changePercentage": "8.42",
          "estimatedValue": "0.00",
          "last24HoursEstimatedValueChange": "0.00"
        },
        "TMN": {
          "baseMarketName": "TMN",
          "changePercentage": "-1.00",
          "estimatedValue": "0",
          "last24HoursEstimatedValueChange": "0"
        },
        "USDT": {
          "changePercentage": "0.00",
          "estimatedValue": "0.00",
          "last24HoursEstimatedValueChange": "0.00"
        }
      },
      "symbol": "USDT",
      "total": "0"
    }
  },
  "success": true
}
```

</details>
