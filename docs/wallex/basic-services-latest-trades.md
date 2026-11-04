<!-- source: https://developers.wallex.ir/docs/basic-services-latest-trades -->

### لیست معاملات انجام شده

جهت دریافت آخرین معاملات انجام شده، میتوانید از API زیر استفاده کنید. **توجه داشته باشید استفاده از API به طور مکرر جهت دریافت لیست معاملات توصیه نمیشود و ممکن هست با Rate-Limit مواجه شوید.** جهت دریافت لیست آخرین معاملات انجام شده میتوانید به [آموزش سوکت لیست معاملات](./index.md) مراجعه کنید.

```
GET /v1/trades
```

### توضیحات Query-parameters

برای فراخوانی این API باید مارکتی را که قصد دارید تا نتایح آن را ببینید را در Query-parameters در مسیر API ارسال کنید :

| Parameter | Required | Data Type | Example | Description |
| --- | --- | --- | --- | --- |
| symbol | false | string | BTCUSDT | نماد معاملاتی مورد نظر |

### توضیحات Response-Body

توجه داشته باشید که result.latestTrades شامل چندین Object میباشد که هر کدام مشخصات یک معامله انجام شده میباشد.

## 

```
{
  "result": {
    "latestTrades": [
      {
        "symbol": "نماد و پایه بازار",
        "quantity": "حجم مورد معامله",
        "price": "قیمت واحد",
        "sum": "ارزش سفارش که شامل ضریب مقدار در قیمت میباشد",
        "isBuyOrder": "وضعیت خرید یا فروش بودن معامله",
        "timestamp": "تایم استمپ لحظه انجام معامله"
      }
    ]
  },
  "message": "The operation was successful",
  "success": true
}
```
