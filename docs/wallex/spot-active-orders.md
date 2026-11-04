<!-- source: https://developers.wallex.ir/docs/spot-active-orders -->

### لیست سفارشات فعال

این API برای دریافت لیست سفارش‌های فعال (Active Orders) طراحی شده است.  
سفارش‌های فعال، سفارشاتی هستند که هنوز به طور کامل اجرا نشدند یا لغو نشده‌اند.  
این API به شما امکان می‌دهد تا سفارش‌ها فعال خود را به‌صورت لحظه‌ای بررسی کرده و اطلاعات کامل مربوط به آن‌ها را دریافت کنید.  
همچنین با استفاده از فیلترهای مختلف میتوانید نتایج دلخواه خود را فیلتر کنید.  
توجه داشته باشید تمامی فیلترها را باید به‌صورت Query-parameters ارسال کنید

```
GET /v1/account/openOrders
```

### توضیحات Query-parameters

برای فراخوانی این API میتوانید پارارمترهای مختلف خود را به عنوان Query-parameters در مسیر API ارسال کنید :

| Parameter | Example | Data Type | Required | Valid Values | Definition |
| --- | --- | --- | --- | --- | --- |
| symbol | USDTTMN | String | false | — | با ارسال این Query-parameter میتوانید سفارشات را بر اساس مارکت مورد نظر مشاهده کنید |
| page | 1 | Number | false | Numbers ≥ 1 | با ارسال این Query-parameter میتوانید سفارشات را به صورت صفحه‌بندی‌شده مشاهده کنید (برای مثال page=2 برای دریافت صفحه دوم سفارشات) |
| per_page | 10 | Number | false | Numbers ≥ 1 | تعداد سفارشات نمایش داده‌شده در هر صفحه را مشخص می‌کند (برای مثال per_page=20 برای دریافت ۲۰ سفارش در هر صفحه) |

### توضیحات Response-Body

```
{
  "message": "پیام وضعیت پاسخ از سمت سرور",
  "result": {
    "additionalProp1": [
      {
        "active": true,
        "clientOrderId": "شناسه سفارش از سمت کلاینت",
        "created_at": " زمان ایجاد سفارش",
        "executedPercent": 0,
        "executedPrice": "میانگین قیمت اجرای سفارش",
        "executedQty": "مقدار اجرایی‌شده از سفارش",
        "executedSum": "ارزش کل سفارش اجرا شده",
        "fills": [
          {
            "fee": "مقدار کارمزد برای این اجرای خاص",
            "feeAsset": "نوع دارایی کارمزد (مثلاً USDT)",
            "feeCoefficient": "ضریب کارمزد کلی",
            "isBuyer": "وضعیت خرید با فروش بودن سفارش",
            "makerFeeCoefficient": "ضریب کارمزد به عنوان Maker",
            "price": "قیمت این اجرای خاص",
            "quantity": "مقدار معامله شده",
            "sum": "جمع ارزش اجرای سفارش",
            "symbol": " نماد معاملاتی (مثلاً BTCUSDT)",
            "takerFeeCoefficient": "ضریب کارمزد به عنوان Taker",
            "timestamp": "زمان دقیق اجرای این بخش از سفارش"
          }
        ],
        "origQty": "مقدار اولیه سفارش",
        "price": " قیمت سفارش",
        "side": "نوع سفارش (buy/sell)",
        "status": "وضعیت سفارش (مثل: NEW، FILLED، CANCELED)",
        "stopPrice": "قیمت توقف (برای سفارشات شرطی)",
        "stopPriceCondition": "شرط اجرا شدن stopPrice",
        "sum": " جمع کلی ارزش سفارش",
        "symbol": " نماد معاملاتی مربوط به سفارش",
        "transactTime": 0,
        "type": "نوع سفارش (مثل: LIMIT، MARKET، STOP_LIMIT)",
        "updated_at": " زمان آخرین به‌روزرسانی سفارش"
      }
    ],
    "additionalProp2": ["ساختاری مشابه additionalProp1"],
    "additionalProp3": ["ساختاری مشابه additionalProp1"]
  },
  "result_info": "اطلاعات یا توضیحات اضافی ",
  "success": true
}
```
