<!-- source: https://developers.wallex.ir/docs/trade-credit-connect-wallet -->

### اتصال کیف پول اصلی به اکانت اعتبار معاملاتی

برای متصل کردن کیف پول اصلی به اکانت اعتبار معاملاتی میتوانید از API زیر استفاده کنید.  
به یاد داشته باشید که به منظور این کار باید id اکانت اعتبار معاملاتی خود را که در [زمان ساخت](./trade-credit-activate-sub-account.md) دریافت کردید را در Request-Header ارسال کنید

```
POST /v1/prop/user/packages/connect-to-wallet
```

### توضیحات Request-Body

برای فراخوانی این API باید اطلاعات زیر را به‌صورت JSON در Request-Body ارسال کنید:

| Parameter | Example | Data Type | Required | Valid Values | Definition |
| --- | --- | --- | --- | --- | --- |
| credit | "30000" | String | true | — | مبلغ در هر انتقال (اگر پکیج دریافتی بر پایه تومان باشد، 30000 تومان در هر انتقال منتقل می‌شود) |
| currency | "TMN" | String | true | TMN \| USDT | واحد انتقال (در پکیج‌های تومانی واحد انتقال باید تومانی باشد و در پکیج‌های تتری واحد انتقال باید تتر باشد) |
| usageCount | 3 | Number | true | — | حداکثر تعداد دفعات انتقال |

### توضیحات Request-Header

| Parameter | Example | Data Type | Required | Definition |
| --- | --- | --- | --- | --- |
| sub_account_client_id | "test-123" | String | true | id اکانت اعتبار معاملاتی |

### توضیحات Response-Body

```
{
  "message": "اتصال کیف پول با موفقیت انجام شد",
  "result": {
    "credit": "مقدار انتقال",
    "currency": "ارز پایه",
    "status": "وضعیت",
    "usageCount": "تعداد دفعات انتقال",
    "usedCount": "تعداد انتقال های انجام شده"
  },
  "success": "موفقیت آمیز بودن درخواست"
}
```
