<!-- source: https://developers.wallex.ir/docs/otc-create-order -->

### ثبت سفارش در بازار آنی

به منظور ثبت سفارش جدید در بازار معاملاتی آنی ، میتوانید از API زیر استفاده کنید.

```
POST /v1/account/easy-trade/orders
```

### توضیحات Request-Body

| Parameter | Example | Data Type | Required | Valid Values | Definition |
| --- | --- | --- | --- | --- | --- |
| side | BUY | string | true | BUY \| SELL | جهت تعیین سمت سفارش خود ارسال این مقدار الزامی می‌باشد |
| symbol | BTCUSDT | String | true | — | جهت دریافت قیمت باید نام مارکت را ارسال کنید |
| quantity | 10 | Number | true | — | مقدار حجمی که قصد خریداری کوین را دارید |
| from | otc | String | true | — | جهت ثبت سفارش در بازار معاملاتی آنی باید این مقدار را ارسال کنید |

### توضیحات Response-Body

```
{
  "symbol": "نام ارز معامله شونده و پایه بازار",
  "sourceMarket": "ارز معامله شونده",
  "destinationMarket": "پایه بازار",
  "type": "OTC",
  "side": "سمت معامله",
  "clientOrderId": "شناسه یکتای سفارش ",
  "transactTime": "زمان معامله",
  "price": "قیمت واحد",
  "origQty": "تعداد ارز معامله شده",
  "executedSum": "حجم معامله به پایه بازار",
  "executedQty": "جچم معامله به ارز معامله شونده",
  "executedPrice": "قیمتی که در آن معامله انجام شده است.",
  "sum": "مجموع حجم معامله",
  "executedPercent": "درصد اجرا شده",
  "status": "وضعیت سفارش",
  "active": "وضعیت فعال بودن سفارش",
  "fills": [
    {
      "price": "قیمت",
      "quantity": "حجم",
      "fee": "کامزد",
      "feeCoefficient": "ضریب کارمزد",
      "feeAsset": {},
      "timestamp": "زمان انجام معامله",
      "symbol": "نام ارز معامله شومده و پایه بازار",
      "sum": "مجموع حجم معامله",
      "makerFeeCoefficient": "ضریب کارمزد میکر",
      "takerFeeCoefficient": "ضریب کارمزد تیکر",
      "isBuyer": "وضعیت خرید یا فروش بودن"
    }
  ]
}
```
