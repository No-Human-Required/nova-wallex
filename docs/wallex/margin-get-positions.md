<!-- source: https://developers.wallex.ir/docs/margin-get-positions -->

### دریافت موقعیت‌های تعهدی

شما میتوانید با استفاده از API زیر، موقعیت‌های تعهدی خود را مشاهده کنید. همچنین با استفاده از فیلترهای مختلف میتوانید نتایج دلخواه خود را فیلتر کنید. توجه داشته باشید تمامی فیلترها را باید به‌صورت Query-parameters ارسال کنید

```
GET /margin-trade/v1/positions
```

### توضیحات Query-parameters

برای فراخوانی این API میتوانید پارارمترهای مختلف خود را به عنوان Query-parameters در مسیر API ارسال کنید :

| Parameter | Example | Data Type | Required | Valid Values | Definition |
| --- | --- | --- | --- | --- | --- |
| active | true | boolean | false | true \| false | با ارسال این Query-parameter میتوانید موقعیت‌های خود را بر اساس فعال یا غیرفعال بودن فیلتر کنید |
| position_side | long | String | false | long \| short | با ارسال این Query-parameter میتوانید موقعیت‌های خود را بر اساس long یا short بودن فیلتر کنید |
| market | BTCUSDT | String | false | — | با ارسال این Query-parameter میتوانید موقعیت‌های خود را بر اساس مارکت آن‌ها فیلتر کنید |

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
    "created_at": " زمان ساختن سفارش",
    "expires_at": "تاریخ منقضی شدن",
    "extend_time": "(هر ۴ ساعت)",
    "first_order_filled": " اولین سفارش پوزیشن ب فیلد شدن آن",
    "id": " ایدی سفارش",
    "interest": {
      "currency": "ارز",
      "value": " ارزش کارمزد"
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
    "updated_at": "نمایش دهنده زمان بروزرسانی وثیقه یا حد سود و ضرر",
    "success": "موفقیت آمیز بودن درخواست"
  }
}
```
