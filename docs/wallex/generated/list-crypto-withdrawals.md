<!-- source: https://developers.wallex.ir/docs/generated/list-crypto-withdrawals -->

# دریافت فهرست برداشت‌های رمزارز

`GET /v1/account/crypto-withdrawal`

**Base URL:** `https://api.wallex.com`

فهرست صفحه‌بندی‌شدهٔ برداشت‌های رمزارز کاربر. نیازمند دسترسی GENERAL و سطح کاربری ۱ است. وضعیت‌های نمایش‌داده‌شده در پاسخ فهرست شامل Accomplished، InProgress و Rejected هستند.

**Tags:** basic-services

## Authentication

- `ApiKeyAuth` — apiKey in header `x-api-key`

## Parameters

| Name | In | Type | Required | Description |
| --- | --- | --- | --- | --- |
| `asset` | query | string |  | نماد رمزارز، مانند USDT |
| `wallet_address` | query | string |  | آدرس کیف‌پول مقصد |
| `memo` | query | string |  | ممو یا تگ مقصد |
| `network_id` | query | string |  | شناسهٔ شبکه |
| `from_date` | query | string |  | شروع بازه با قالب YYYY-MM-DDTHH:mm:ssZ |
| `to_date` | query | string |  | پایان بازه با قالب YYYY-MM-DDTHH:mm:ssZ |
| `per_page` | query | integer |  | تعداد نتیجه در هر صفحه؛ حداکثر ۲۰ |
| `page` | query | integer |  | شمارهٔ صفحه |

## Responses

### default — ساختار و کد پاسخ در مجموعهٔ ارسالی مشخص نشده است.
