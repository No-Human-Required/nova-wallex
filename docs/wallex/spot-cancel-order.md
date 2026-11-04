<!-- source: https://developers.wallex.ir/docs/spot-cancel-order -->

### لغو سفارش

در صورتی که وضعیت سفارش شما هنوز FINISHED نشده باشد. به عبارت دیگر درصورتی که سفارش شما به‌طور کامل اجرا نشده باشد و یا قسمتی از آن اجرا شده باشد. شما میتوانید سفارش خود را با API زیر لغو کنید.  
توجه داشته باشید که Client-Order-id خود را باید به عنوان path-variable ارسال کنید.

```
DELETE /v1/account/orders/{client_id}
```

### توضیحات Path-Variable

برای فراخوانی این API باید Client-Order-id خود را به عنوان path-variable در مسیر API ارسال کنید :

## API Parameters

| Parameter | Example | Data Type | Required | Definition |
| --- | --- | --- | --- | --- |
| clientOrderId | "test-clientId" | String | true | عبارت Client-order-id یک عبارت یکتا می‌باشد که در زمان ساخت سفارش در Response-Body ارسال می‌شود. جهت آشنایی برای گرفتن Client-order-id به قسمت [ثبت سفارش](./spot-create-order.md) مراجعه کنید. |

### توضیحات Response-Body

```
{
  "message": "پیام پاسخ از سرور (مثلا موفقیت یا خطا)",
  "result": {
    "active": "وضعیت فعال بودن سفارش",
    "clientOrderId": "شناسه سفارش اختصاصی مشتری",
    "created_at": "زمان ایجاد سفارش (مثلا به صورت رشته تاریخ)",
    "executedPercent": "درصد اجراشده از سفارش شما",
    "executedPrice": "قیمت اجرا شده سفارش",
    "executedQty": "مقدار اجرا شده از سفارش",
    "executedSum": "مجموع مقدار اجرا شده ",
    "fee": "هزینه انجام سفارش",
    "fills": [
      {
        "fee": "کارمزد هر معامله",
        "feeAsset": " کارمزد به چه ارزی پرداخت شده",
        "feeCoefficient": "ضریب هزینه معامله",
        "isBuyer": "وضعیت خرید با فروش بودن سفارش",
        "makerFeeCoefficient": "ضریب کارمزد میکر",
        "price": "قیمت معامله",
        "quantity": "مقدار معامله شده",
        "sum": "مجموع معامله",
        "symbol": "نماد معامله",
        "takerFeeCoefficient": "ضریب کارمزد  ",
        "timestamp": "زمان معامله"
      }
    ],
    "origQty": "مقدار اصلی سفارش ثبت شده",
    "price": "قیمت ثبت شده سفارش",
    "side": "سمت سفارش: خرید یا فروش",
    "status": "وضعیت سفارش (مثلا فعال، لغو شده، تکمیل شده)",
    "stopPrice": "قیمت توقف",
    "stopPriceCondition": "شرط فعال‌سازی قیمت توقف",
    "sum": "مجموع کل سفارش ",
    "symbol": " نماد معاملاتی سفارش",
    "transactTime": 0,
    "type": " نوع سفارش ",
    "updated_at": "زمان آخرین به‌روزرسانی سفارش"
  },
  "success": true
}
```
