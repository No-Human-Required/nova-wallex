<!-- source: https://developers.wallex.ir/docs/margin-edit-collateral -->

### ویرایش وثیقه موقعیت تعهدی

شما می‌توانید با استفاده از API زیر، میزان وثیقه موقعیت تعهدی خود را به‌روزرسانی کنید.  
به یاد داشته باشید که به منظور این کار باید id موقعیت تعهدی که در [زمان ساخت](./margin-open-position.md) دریافت کردید را به عنوان Path-Variable ارسال کنید

```
PATCH /margin-trade/v1/positions/{id}/collateral
```

### توضیحات Request-Body

برای فراخوانی این API باید اطلاعات زیر را به‌صورت JSON در Request-Body ارسال کنید:

| Parameter | Example | Data Type | Required | Definition |
| --- | --- | --- | --- | --- |
| change | "82494" | String | true | میزان مبلغ درخواستی برای افزایش وثیقه |

### توضیحات Path-Variable

برای فراخوانی این API باید ID موقعیت تعهدی خود را در Path-Variable ارسال کنید

| Parameter | Example | Data Type | Required | Definition |
| --- | --- | --- | --- | --- |
| id | "10" | number | true | هر موقعیت تعهدی یک ID یکتا دارد که برای افزایش وثیقه باید در این API ارسال شود |

### توضیحات Response-Body

```
{
  "result": {
    "call_price": "حد هشدار",
    "close_filled_price": "قیمت بسته شدن",
    "close_price": "قیمت بستن",
    "close_reason": "علت بستن",
    "closed_at": "زمان بسته شدن",
    "collateral": {
      "currency": "ارز",
      "value": "ارزش وثیقه"
    },
    "created_at": " زمان ایجاد سفارش",
    "expires_at": "زمان منقضی شدن",
    "extend_time": "زمان تمدید",
    "first_order_filled": "اولین سفارش انجام شده",
    "id": " ایدی سفارش",
    "interest": {
      "currency": "ارز",
      "value": "ارزش کارمزد"
    },
    "is_called": "به حد هشدار رسیده است یا خیر",
    "liquidity_price": "قیمت لیکوییدیتی",
    "loan": {
      "currency": "ارز",
      "value": "ارزش وام",
      "market": "نام جفت ارز",
      "max_age": "حداکثر عمر موقعیت",
      "open_filled_price": "قیمت باز شدن سفارش",
      "open_price": "قیمت واحد",
      "opened_at": "زمان ایجاد سفارش",
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
      "updated_at": "نمایش دهنده زمان بروزرسانی وثیقه یا حد سود و ضرر",
      "success": "وموفقیت آمیز بودن درخواست"
    }
  }
}
```
