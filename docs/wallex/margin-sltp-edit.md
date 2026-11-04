<!-- source: https://developers.wallex.ir/docs/margin-sltp-edit -->

### ویرایش حد سود و حد ضرر موقعیت تعهدی

با استفاده از این API می‌توانید قیمت‌های حد ضرر (Stop-Loss) و حد سود (Take-Profit) موقعیت تعهدی خود را به‌روزرسانی کنید.  
به یاد داشته باشید که به منظور این کار باید id موقعیت تعهدی که در [زمان ساخت](./margin-open-position.md) دریافت کردید را به عنوان Path-Variable ارسال کنید

```
PATCH /margin-trade/v1/positions/{id}/sltp
```

### توضیحات Request-Body

برای فراخوانی این API باید اطلاعات زیر را به‌صورت JSON در Request-Body ارسال کنید:

| Parameter | Example | Data Type | Required | Definition |
| --- | --- | --- | --- | --- |
| stop_loss | "82494" | String | false | میزان حد ضرر مشخص شده برای موقعیت تعهدی |
| take_profit | "82494" | String | false | میزان حد سود مشخص شده برای موقعیت تعهدی |

### توضیحات Path-Variable

برای فراخوانی این API باید ID موقعیت تعهدی خود را در Path-Variable ارسال کنید

| Parameter | Example | Data Type | Required | Definition |
| --- | --- | --- | --- | --- |
| id | "10" | number | true | هر موقعیت تعهدی یک ID یکتا دارد که برای تغییر حد سود یا ضرر باید در این API ارسال شود |

### توضیحات Response-Body

```
{
  "result": {
    "call_price": "حد هشدار",
    "close_filled_price": "قیمت بسته شدن سفارش",
    "close_price": "قیمت بسته شدن",
    "close_reason": "علت بستن",
    "closed_at": "زمان بسته شدن",
    "collateral": {
      "currency": "ارز",
      "value": "ارزش وثیقه"
    },
    "created_at": " زمان ساختن سفارش",
    "expires_at": "تاریخ منقضی شدن",
    "extend_time": "(هر ۴ ساعت)",
    "first_order_filled": " اولین سفارش پوزیشن ب فیلد شدن آن",
    "id": " ایدی سفارش",
    "interest": {
      "currency": "ارز",
      "value": "ارزش کارمزد"
    },
    "is_called": "به حد هشدار رسیده است یا خیر",
    "liquidity_price": "قیمت لیکوییدیتی",
    "loan": {
      "currency": "ارز",
      "value": "ارزش وام"
    },
    "market": "نام جفت ارز",
    "max_age": "حداکثر عمرموقعیت",
    "open_filled_price": "قیمت باز شدن سفارش",
    "open_price": "قیمت واحد",
    "opened_at": "زمانی که موقعیت ایجاد شده",
    "profit": {
      "currency": "ارز",
      "value": "ارزش سود و ضرر"
    },
    "profit_percentage": "درصد سود و ضرر",
    "risk_coef": "میزان اعتبار",
    "side": "لانگ / شورت",
    "state": "وضعیت سفارش",
    "stop_loss": "حد ضرر",
    "take_profit": "حد سود",
    "updated_at": "نمایش دهنده زمان بروزرسانی وثیقه یا حد سود و ضرر"
  },
  "success": "موفقیت آمیز بودن درخواست"
}
```
