<!-- source: https://developers.wallex.ir/docs/margin-close-position -->

### بستن موقعیت تعهدی

درصورتی که قصد بستن موقعیت تعهدی خود در قیمت مشخص را دارید میتوانید از API زیر استفاده کنید.  
به یاد داشته باشید که به منظور این کار باید id موقعیت تعهدی که در [زمان ساخت](./margin-open-position.md) دریافت کردید را به عنوان Path-Variable ارسال کنید

```
PATCH /margin-trade/v1/positions/{id}/close
```

### توضیحات Request-Body

برای فراخوانی این API باید اطلاعات زیر را به‌صورت JSON در Request-Body ارسال کنید:

| Parameter | Example | Data Type | Required | Definition |
| --- | --- | --- | --- | --- |
| price | "82494" | String | true | قیمت واحدی که قصد دارید موقعیت تعهدی خود را ببندید |

### توضیحات Path-Variable

برای فراخوانی این API باید ID موقعیت تعهدی خود را در Path-Variable ارسال کنید

| ` | Parameter | Example | Data Type | Required / Optional | Definition |
| --- | --- | --- | --- | --- | --- |
| id | "10" | number | Required | هر موقعیت تعهدی یک ID یکتا دارد که برای بستن موقعیت تعهدی باید در این API ارسال شود |  |

### توضیحات Response-Body

```
{
  "result": {
    "call_price": "حد هشدار",
    "close_filled_price": "قیمت بسته سفارش",
    "close_price": "قیمت بسته شدن",
    "close_reason": "علت بستن",
    "closed_at": "زمان بسته شدن",
    "collateral": {
      "currency": " ارز",
      "value": "ارزش وثیقه",
      "created_at": " زمان ساختن سفارش",
      "expires_at": "تاریخ منقضی شدن",
      "extend_time": "زمان تمدید",
      "first_order_filled": " اولین سفارش انجام شده",
      "id": " ایدی سفارش",
      "interest": {
        "currency": "ارز",
        "value": "ارزش کارمزد"
      },
      "is_called": "به حد هشدار رسیده است یا خیر",
      "liquidity_price": "قیمت لیکوییدیتی",
      "loan": {
        "currency": "ارز",
        "value": " ارزش وام"
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
}
```
