<!-- source: https://developers.wallex.ir/docs/trade-credit-close-sub-account -->

### بستن اکانت اعتبار معاملاتی

برای بستن اکانت اعتبار معاملاتی خود میتوانید از API زیر استفاده کنید.  
به یاد داشته باشید که به منظور این کار باید id اکانت اعتبار معاملاتی خود را که در [زمان ساخت](./trade-credit-activate-sub-account.md) دریافت کردید را در Request-Header ارسال کنید

```
DELETE /v1/prop/user/packages
```

### توضیحات Request-Header

| Parameter | Example | Data Type | Required / Optional | Definition |
| --- | --- | --- | --- | --- |
| sub_account_client_id | "test-123" | String | Required | id اکانت اعتبار معاملاتی |

### توضیحات Response-Body

```
{
  "result": {
    "client_id": "شناسه حساب فرعی",
    "start_balance": "دارایی اولیه طرح",
    "final_balance": "دارایی باقی مانده طرح",
    "final_balance_without_transfers": "دارایی باقی مانده بدون در نظر گرفتن انتقال ها",
    "currency": "ارز پایه",
    "prop_package_id": " شناسه پکیج",
    "user_id": "شناسه کاربر"
  }
}
```
