<!-- source: https://developers.wallex.ir/docs/basic-services-account-fee -->

### سطح کاربری و کارمزد

جهت دریافت سطح کاربری و کارمزد اکانت خود ، میتوانید از API زیر استفاده کنید.

```
GET /v1/account/fee
```

### توضیحات Response-Body

## 

```
{
  "result": {
    "SHIBTMN": {
      "makerFeeRate": "ضریب کارمزد میکر",
      "takerFeeRate": "ضریب کارمزد تیکر",
      "recent_days_sum": "حجم معاملاتی"
    }
  }
}
```
