<!-- source: https://developers.wallex.ir/docs/generated/get-crypto-withdrawal -->

# دریافت جزئیات برداشت رمزارز

`GET /v1/account/crypto-withdrawal/{withdrawal_id}`

**Base URL:** `https://api.wallex.com`

جزئیات یک برداشت رمزارز. نیازمند دسترسی GENERAL و سطح کاربری ۲ است. اگر برداشت متعلق به کاربر نباشد، result خالی برمی‌گردد.

**Tags:** basic-services

## Authentication

- `ApiKeyAuth` — apiKey in header `x-api-key`

## Parameters

| Name | In | Type | Required | Description |
| --- | --- | --- | --- | --- |
| `withdrawal_id` | path | string | yes | شناسهٔ برداشت |

## Responses

### default — ساختار و کد پاسخ در مجموعهٔ ارسالی مشخص نشده است.
