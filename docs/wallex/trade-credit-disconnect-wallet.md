<!-- source: https://developers.wallex.ir/docs/trade-credit-disconnect-wallet -->

### قطع اتصال کیف پول اصلی از اکانت اعتبار معاملاتی

برای قطع اتصال کردن کیف پول اصلی از اکانت اعتبار معاملاتی میتوانید از API زیر استفاده کنید.  
به یاد داشته باشید که به منظور این کار باید id اکانت اعتبار معاملاتی خود را که در [زمان ساخت](./trade-credit-activate-sub-account.md) دریافت کردید را در Request-Header ارسال کنید

```
DELETE /v1/prop/user/packages/connect-to-wallet
```

### توضیحات Request-Header

| Parameter | Example | Data Type | Required | Definition |
| --- | --- | --- | --- | --- |
| sub_account_client_id | "test-123" | String | true | id اکانت اعتبار معاملاتی |

### توضیحات Response-Body

```
{
  "result": "[]",
  "message": "قطع اتصال کیف پول با موفقیت انجام شد",
  "success": "موفقیت آمیز بودن درخواست"
}
```
