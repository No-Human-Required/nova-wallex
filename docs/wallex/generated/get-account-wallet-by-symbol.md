<!-- source: https://developers.wallex.ir/docs/generated/get-account-wallet-by-symbol -->

# دریافت آدرس کیف‌پول کاربر برای نماد مشخص

`GET /v1/account/wallets/{symbol}`

**Base URL:** `https://api.wallex.com`

این API آدرس کیف‌پول مربوط به ارز مورد نظر را بر اساس شبکه انتخاب‌شده (مانند ERC20) بازمی‌گرداند. نیازمند API Key در هدر است.

**Tags:** basic-services

## Authentication

- `ApiKeyAuth` — apiKey in header `x-api-key`

## Parameters

| Name | In | Type | Required | Description |
| --- | --- | --- | --- | --- |
| `symbol` | path | string | yes | نماد ارز دیجیتال مورد نظر (مانند ETH) (example: `eth`) |
| `network` | query | string |  | شبکه مورد نظر برای دریافت آدرس (مثلاً ERC20 یا TRC20) (example: `erc20`) |

## Responses

### 200 — پاسخ موفق

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `result` | object |  |  |
| `result.coin_type` | object |  |  |
| `result.coin_type.key` | string |  |  (example: `"ETH"`) |
| `result.coin_type.name` | string |  |  (example: `"اتریوم"`) |
| `result.coin_type.name_en` | string |  |  (example: `"Ethereum"`) |
| `result.coin_type.type` | string |  |  (example: `"CRYPTO"`) |
| `result.coin_type.deposit_availability` | string |  |  (example: `"ENABLE"`) |
| `result.coin_type.withdrawal_availability` | string |  |  (example: `"ENABLE"`) |
| `result.coin_type.deposit_unavailability_reason` | string |  |  |
| `result.coin_type.withdrawal_unavailability_reason` | string |  |  |
| `result.wallets` | object |  |  |
| `result.wallets.{key}.network` | object |  |  |
| `result.wallets.{key}.network.id` | integer |  |  (example: `4`) |
| `result.wallets.{key}.network.name` | string |  |  (example: `"ERC20"`) |
| `result.wallets.{key}.network.message` | string |  |  |
| `result.wallets.{key}.network.type` | string |  |  (example: `"ADDRESS"`) |
| `result.wallets.{key}.network.deposit_availability` | string |  |  (example: `"ENABLE"`) |
| `result.wallets.{key}.network.withdrawal_availability` | string |  |  (example: `"ENABLE"`) |
| `result.wallets.{key}.network.deposit_unavailability_reason` | string |  |  |
| `result.wallets.{key}.network.withdrawal_unavailability_reason` | string |  |  |
| `result.wallets.{key}.address` | string |  |  (example: `"0xa1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0"`) |
| `result.wallets.{key}.memo` | string |  |  |
| `result.wallets.{key}.expire_at` | string <date-time> |  |  (example: `"2026-02-21 08:44:47"`) |
| `result.wallets.{key}.min_confirmation` | integer |  |  (example: `10`) |
| `result.wallets.{key}.transaction_fee` | number <float> |  |  (example: `0.003`) |
| `result.wallets.{key}.min_withdrawal_value` | string |  |  (example: `"0.005"`) |
| `result.wallets.{key}.min_deposit_value` | number |  |  (example: `0.001`) |
| `message` | string |  |  (example: `"The operation was successful"`) |
| `success` | boolean |  |  (example: `true`) |
| `provider` | string |  |  (example: `"trade"`) |

<details><summary>Example / shape</summary>

```json
{
  "result": {
    "coin_type": {
      "key": "ETH",
      "name": "اتریوم",
      "name_en": "Ethereum",
      "type": "CRYPTO",
      "deposit_availability": "ENABLE",
      "withdrawal_availability": "ENABLE",
      "deposit_unavailability_reason": null,
      "withdrawal_unavailability_reason": null
    },
    "wallets": {
      "<key>": {
        "network": {
          "id": 4,
          "name": "ERC20",
          "message": null,
          "type": "ADDRESS",
          "deposit_availability": "ENABLE",
          "withdrawal_availability": "ENABLE",
          "deposit_unavailability_reason": null,
          "withdrawal_unavailability_reason": null
        },
        "address": "0xa1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0",
        "memo": null,
        "expire_at": "2026-02-21 08:44:47",
        "min_confirmation": 10,
        "transaction_fee": 0.003,
        "min_withdrawal_value": "0.005",
        "min_deposit_value": 0.001
      }
    }
  },
  "message": "The operation was successful",
  "success": true,
  "provider": "trade"
}
```

</details>
