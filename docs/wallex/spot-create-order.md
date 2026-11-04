<!-- source: https://developers.wallex.ir/docs/spot-create-order -->

### ثبت سفارش

این API برای ثبت سفارش جدید در بازار اسپات استفاده می‌شود. کاربر می‌تواند با مشخص کردن پارامترهای سفارش مثل نوع، قیمت، مقدار، و نماد معاملاتی، سفارش خود را ثبت کند.

```
POST /v1/account/orders
```

#### توضیحات Request-Body

برای فراخوانی این API باید اطلاعات زیر را به‌صورت JSON در Request-Body ارسال کنید:

## API Parameters

| Parameter | Example | Data Type | Required | Valid Values | Definition |
| --- | --- | --- | --- | --- | --- |
| price | "82494" | String | true | — | قیمت واحد برای ثبت سفارش |
| quantity | "10" | String | true | — | حجم درخواستی برای ثبت سفارش |
| side | "BUY" | String | true | "BUY" \| "SELL" | با توجه به سمت سفارش شما (خرید یا فروش) این پارامتر باید یکی از دو نوع گفته شده باشد |
| symbol | "BTCUSDT" | String | true | — | بازاری که قصد دارید تا در آن سفارش ثبت شود |
| type | "LIMIT" | String | true | "LIMIT" \| "MARKET" \| "STOP_LIMIT" \| "STOP_MARKET" | با توجه به نوع سفارش شما این پارامتر باید یکی از چهار نوع سفارش گفته شده باشد |
| stop_Price | "83000" | String | Conditional | — | در صورتی که سفارش شما از نوع "STOP_LIMIT" یا "STOP_MARKET" باشد ارسال این فیلد الزامی است و در غیر این صورت نباید ارسال شود. این فیلد بیانگر قیمت توقف می‌باشد. |
| client_id | "test_clientId" | String | false | letters (A–Z), underscore(_), digits (0–9) | در صورت عدم ارسال، clientOrderId توسط سیستم ساخته می‌شود. در صورت ارسال باید مقدار unique باشد، در غیر این صورت سفارش ثبت نمی‌شود. |

#### توضیحات Response-Body

در صورت موفقیت آمیزبودن درخواست شما ، Response-Code دریافتی 201 میباشد.

```
{
  "message": "پیام کلی درباره وضعیت سفارش یا پاسخ سرور",
  "result": {
    "active": "آیا سفارش فعال است یا خیر",
    "clientOrderId": "شناسه سفارش که برای دریافت جزییات سفارش یا لغو آن استفاده میگردد",
    "created_at": "زمان ایجاد سفارش",
    "executedPercent": "درصد اجراشده از سفارش",
    "executedPrice": " قیمت اجرا شده سفارش ",
    "executedQty": "مقدار اجرا شده از سفارش",
    "executedSum": "جمع مبلغ اجرا شده سفارش ",
    "fee": "کارمزد کل سفارش",
    "fills": [
      {
        "fee": "کارمزد بخش اجرا شده",
        "feeAsset": "نوع دارایی کارمزد (مثل USDT)",
        "feeCoefficient": "ضریب کارمزد آن بخش",
        "isBuyer": "آیا کاربر خریدار بود یا فروشنده",
        "makerFeeCoefficient": "ضریب کارمزد Maker",
        "price": "قیمت معامله در آن بخش",
        "quantity": "حجم معامله در آن بخش",
        "sum": "جمع کل مبلغ معامله در آن بخش",
        "symbol": "نماد معاملاتی مربوط به معامله",
        "takerFeeCoefficient": "ضریب کارمزد Taker",
        "timestamp": " زمان انجام معامله در آن بخش"
      }
    ],
    "origQty": "مقدار اولیه سفارش",
    "price": "قیمت سفارش",
    "side": "سمت سفارش",
    "status": "وضعیت سفارش",
    "stopPrice": "قیمت توقف",
    "stopPriceCondition": "شرط مربوط به قیمت توقف",
    "sum": "جمع کل ارزش سفارش",
    "symbol": "نماد معاملاتی سفارش",
    "transactTime": "زمان تراکنش ",
    "type": "نوع سفارش ",
    "updated_at": "زمان آخرین به‌روزرسانی سفارش"
  },
  "success": "موفقیت آمیز بودن درخواست"
}
```

> **محدودیت نرخ ثبت سفارش**
>
> تعداد درخواست‌های مجاز برای ثبت سفارش **حداکثر ۲۰ درخواست در هر ۱۰ ثانیه** می‌باشد.
