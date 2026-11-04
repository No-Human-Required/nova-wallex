<!-- source: https://developers.wallex.ir/docs/margin-open-position -->

### ایجاد موقعیت مارجین

شما میتوانید با استفاده از API زیر موقعیت تعهدی جدیدی باز کنید.

```
POST /margin-trade/v1/positions
```

### توضیحات Request-Body

برای فراخوانی این API باید اطلاعات زیر را به‌صورت JSON در Request-Body ارسال کنید:

| Parameter | Example | Data Type | Required | Valid Values | Definition |
| --- | --- | --- | --- | --- | --- |
| collateral | "300000" | String | true | — | میزان وثیقه درخواستی برای ایجاد موقعیت تعهدی |
| market | "BTCUSDT" | String | true | — | مارکتی که قصد دارید در آن موقعیت تعهدی ایجاد کنید |
| open_price | "8900000" | String | true | — | قیمتی که در آن پوزیشن معامله تعهدی ایجاد می‌شود |
| risk_coef | "10" | String | true | — | نسبت اعتباری که قصد دارید دریافت کنید |
| side | long | String | true | long \| short | — |
| stop_loss | "86000" | String | false | — | میزان حد ضرر که موقعیت تعهدی در آن بسته شود |
| take_profit | "86000" | String | false | — | میزان حد سود که موقعیت تعهدی در آن بسته شود |

### توضیحات Response-Body

```
{
  "result": {
    "call_price": "حد هشدار",
    "close_reason": "علت بستن ",
    "collateral": "وثیقه",
    "created_at": " زمان ایجاد سفارش",
    "expires_at": "تاریخ منقضی شدن",
    "extend_time": "زمان تمدید",
    "first_order_filled": " اولین سفارش انجام شده",
    "id": " ایدی سفارش",
    "interest": "کارمزد",
    "is_called": "به حد هشدار رسیده است یا خیر",
    "liquidity_price": "قیمت لیکوییدشدن",
    "loan": "وام",
    "market": "نام جفت ارز",
    "max_age": "حداکثر عمرموقعیت",
    "open_filled_price": "قیمت باز شدن سفارش",
    "open_price": "قیمت واحد",
    "opened_at": "زمانی که موقعیت ایجاد شده",
    "profit": "میزان سود یا ضرر",
    "risk_coef": "نسبت اعتبار",
    "side": " لانگ/شورت",
    "state": "وضعیت سفارش",
    "updated_at": "نمایش دهنده زمان بروزرسانی وثیقه یا حد سود و ضرر",
    "success": "موفقیت آمیز بودن درخواست"
  }
}
```
