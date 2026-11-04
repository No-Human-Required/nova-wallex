<!-- source: https://developers.wallex.ir/docs/spot-order-list -->

### دریافت لیست سفارش‌ها

جهت مشاهده تمامی سفارش‌های خود در والکس میتوانید از این API استفاده کنید.  
با استفاده از فیلترهای مختلف میتوانید نتایج دلخواه خود را دریافت کنید.  
توجه داشته باشید تمامی فیلترها را باید به‌صورت Query-parameters ارسال کنید

```
GET /v1/account/orders
```

### توضیحات Query-parameters

برای فراخوانی این API میتوانید پارارمترهای مختلف خود را به عنوان Query-parameters در مسیر API ارسال کنید :

| Parameter | Example | Data Type | Required | Valid Values | Definition |
| --- | --- | --- | --- | --- | --- |
| from | 2024-10-01 | String | false | — | با ارسال این Query-parameter میتوانید سفارش‌های خود را از تاریخ X دریافت کنید |
| to | 2024-10-02 | String | false | — | با ارسال این Query-parameter میتوانید سفارش‌های خود را تا تاریخ X دریافت کنید |
| page | 1 | Number | false | Numbers ≥ 1 | با ارسال این Query-parameter میتوانید سفارشات را به صورت صفحه‌بندی‌شده مشاهده کنید (برای مثال page=2 برای دریافت صفحه دوم سفارشات) |
| per_page | 10 | Number | false | Numbers ≥ 1 | تعداد سفارشات نمایش داده‌شده در هر صفحه را مشخص می‌کند (برای مثال per_page=20 برای دریافت ۲۰ سفارش در هر صفحه) |
| type | LIMIT | String | false | LIMIT \| MARKET \| STOP_LIMIT \| STOP_MARKET | فیلتر سفارشات بر اساس نوع آن |
| side | BUY | String | false | BUY \| SELL | فیلتر سفارشات بر اساس سمت آن |
| market | BTCUSDT | String | false | — | فیلتر سفارشات بر اساس مارکت |

### توضیحات Response-Body

```
{
  "message": " پیام کلی از سرور درباره وضعیت پاسخ",
  "result": {
    "additionalProp1": [
      {
        "active": "وضعیت فعال بودن سفارش",
        "clientOrderId": "شناسه سفارش در سمت کلاینت",
        "created_at": "زمان ایجاد سفارش",
        "executedPercent": "مقدار اجرا شده از سفارش",
        "executedPrice": "میانگین قیمت سفارش اجرا شده",
        "executedQty": "مقدار سفارش که اجرا شده",
        "executedSum": "جمع مبلغ سفارش اجرا شده",
        "fee": "  کارمزد سفارش",
        "fills": [
          {
            "fee": "کارمزد معامله",
            "feeAsset": "نوع دارایی کارمزد (مثلاً USDT)",
            "feeCoefficient": "ضریب کارمزد",
            "isBuyer": "وضعیت خرید یا فروش بودن سفارش",
            "makerFeeCoefficient": "ضریب کارمزد Maker",
            "price": " قیمت معامله",
            "quantity": " تعداد معامله شده در این قسمت",
            "sum": " مجموع قیمت در این قسمت",
            "symbol": " نماد معاملاتی",
            "takerFeeCoefficient": " ضریب کارمزد Taker",
            "timestamp": "زمان اجرای این بخش"
          }
        ],
        "origQty": "مقدار اولیه سفارش",
        "price": " قیمت سفارش",
        "side": "نوع سفارش (buy یا sell)",
        "status": "وضعیت سفارش (مثلاً NEW، FILLED، CANCELED)",
        "stopPrice": "قیمت توقف (در صورت سفارش شرطی)",
        "stopPriceCondition": " شرط اجرای قیمت توقف",
        "sum": "جمع کل ارزش سفارش",
        "symbol": " نماد معاملاتی سفارش",
        "transactTime": 0,
        "type": "نوع سفارش (LIMIT, MARKET, STOP_LIMIT و...)",
        "updated_at": "زمان آخرین به‌روزرسانی سفارش"
      }
    ],
    "additionalProp2": ["ساختاری مشابه additionalProp1"],
    "additionalProp3": ["ساختاری مشابه additionalProp1"]
  },
  "result_info": "اطلاعات اضافی درباره نتیجه (مثل پیغام یا توضیح)",
  "success": true
}
```
