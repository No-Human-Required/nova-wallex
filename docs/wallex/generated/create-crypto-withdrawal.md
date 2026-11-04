<!-- source: https://developers.wallex.ir/docs/generated/create-crypto-withdrawal -->

# ثبت درخواست برداشت رمزارز

`POST /v1/account/crypto-withdrawal`

**Base URL:** `https://api.wallex.com`

ثبت درخواست برداشت رمزارز با API Key. نیازمند دسترسی‌های GENERAL و WITHDRAWAL و سطح کاربری ۲ است. برای این درخواست OTP لازم نیست. محدودیت نرخ: ۶ درخواست در دقیقه. درخواست از IP ایران یا IP خصوصی رد می‌شود و در صورت تعریف فهرست IP مجاز برای کلید، فقط همان IPها پذیرفته می‌شوند. تا ۲۴ ساعت پس از تغییر رمز عبور یا تغییر روش ورود دومرحله‌ای، درخواست برداشت حتی با API Key پذیرفته نمی‌شود.

**Tags:** basic-services

## Authentication

- `ApiKeyAuth` — apiKey in header `x-api-key`

## Request body

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `coin` | string | yes | نماد رمزارز (example: `"USDT"`) |
| `network` | string | yes | نام شبکه؛ از /v1/networks یا /v1/currencies قابل بررسی است (example: `"TRC20"`) |
| `value` | string | yes | مقدار برداشت؛ باید بزرگ‌تر از صفر باشد. در نمونهٔ ارسالی به‌شکل رشته است (example: `"10"`) |
| `wallet_address` | string | yes | آدرس کیف‌پول مقصد؛ مقدار نمونه باید با آدرس واقعی جایگزین شود (example: `"T..."`) |
| `memo` | string |  | ممو یا تگ مقصد برای شبکه‌هایی که به آن نیاز دارند؛ می‌تواند null باشد |
| `client_unique_id` | string |  | اختیاری و nullable؛ برای جلوگیری از ثبت برداشت تکراری مقدار مشخصی بفرستید. اگر همان کاربر دوباره همان مقدار را بفرستد، همان برداشت قبلی برمی‌گردد. (example: `"my-unique-id-001"`) |

**Example:**

```json
{
  "coin": "USDT",
  "network": "TRC20",
  "value": "10",
  "wallet_address": "T...",
  "memo": "string",
  "client_unique_id": "my-unique-id-001"
}
```

## Responses

### default — ساختار و کد پاسخ در مجموعهٔ ارسالی مشخص نشده است.
