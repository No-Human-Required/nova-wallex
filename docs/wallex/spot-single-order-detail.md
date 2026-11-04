<!-- source: https://developers.wallex.ir/docs/spot-single-order-detail -->

### دریافت جزئیات سفارش

برای مشاهده جزئیات یک سفارش میتوانید از API زیر استفاده کنید. این جزئیات شامل وضعیت سفارش، مقدار پر شده، کارمزدها و ... سفارش شما میباشد.  
توجه داشته باشید که Client-Order-id خود را باید به عنوان path-variable ارسال کنید.

```
GET /v1/account/orders/{client_id}
```

### توضیحات Path-Variable

برای فراخوانی این API باید Client-Order-id خود را به عنوان path-variable در مسیر API ارسال کنید :

| Parameter | Example | Data Type | Required | Definition |
| --- | --- | --- | --- | --- |
| clientOrderId | "test-clientId" | String | true | عبارت Client-order-id یک عبارت یکتا می‌باشد که در زمان ساخت سفارش در Response-Body ساخت سفارش دریافت می‌شود. جهت آشنایی برای گرفتن Client-order-id به قسمت [ثبت سفارش](./spot-create-order.md) مراجعه کنید. |

## 

### توضیحات Response-Body

```
{
  "message": "پیام متنی درباره وضعیت پاسخ",
  "result": {
    "active": "وضعیت فعال بودن سفارش",
    "clientOrderId": "شناسه سفارش اختصاصی مشتری",
    "created_at": "زمان ایجاد سفارش (رشته تاریخ و زمان)",
    "executedPercent": 0,
    "executedPrice": "قیمت اجرا شده سفارش",
    "executedQty": "تعداد اجرا شده از سفارش",
    "executedSum": "مجموع مبلغ اجرا شده",
    "fee": "کارمزد کل سفارش",
    "fills": [
      {
        "fee": "کارمزد این معامله خاص",
        "feeAsset": "نوع دارایی که کارمزد به آن تعلق گرفته",
        "feeCoefficient": "ضریب کارمزد",
        "isBuyer": "وضعیت خرید با فروش بودن سفارش",
        "makerFeeCoefficient": "ضریب کارمزد سازنده سفارش",
        "price": "قیمت معامله",
        "quantity": " تعداد معامله شده",
        "sum": "مجموع مبلغ معامله",
        "symbol": "نماد دارایی معامله شده",
        "takerFeeCoefficient": "ضریب کارمزد گیرنده سفارش",
        "timestamp": "زمان معامله"
      }
    ],
    "origQty": " تعداد اولیه سفارش",
    "price": " قیمت سفارش",
    "side": " وضعیت سفارش ",
    "stopPrice": "قیمت توقف سفارش ",
    "stopPriceCondition": "شرط فعال شدن قیمت توقف",
    "sum": "مجموع کل سفارش",
    "symbol": "نماد دارایی مربوط به سفارش",
    "transactTime": 0,
    "type": " نوع سفارش ",
    "updated_at": " زمان آخرین به‌روزرسانی سفارش"
  },
  "success": true
}
```
