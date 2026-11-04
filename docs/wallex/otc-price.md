<!-- source: https://developers.wallex.ir/docs/otc-price -->

### دریافت قیمت ها در بازار آنی

جهت دریافت قیمت ها در بازار معاملاتی آنی میتوانید از API زیر استفاده کنید. به منظور این کار باید نماد و سمت معامله به عنوان Query-Param ارسال کنید

```
GET /v1/account/otc/price
```

### توضیحات Query-parameters

برای فراخوانی این API میتوانید پارارمترهای مختلف خود را به عنوان Query-parameters در مسیر API ارسال کنید :

| Parameter | Example | Data Type | Required | Valid Values | Definition |
| --- | --- | --- | --- | --- | --- |
| side | BUY | string | true | BUY \| SELL | جهت تعیین سمت سفارش خود، ارسال این مقدار الزامی می‌باشد |
| symbol | BTCUSDT | String | true | — | جهت دریافت قیمت باید نام مارکت را ارسال کنید |

### توضیحات Response-Body

```
{
  "result": {
    "price": "قیمت",
    "price_expires_at": "تاریخ منقضی شدن قیمت",
    "ttl": "ttl",
    "current_time": "زمان اکنون"
  },
  "message": "عملیات با موفقیت انجام شد",
  "success": true
}
```
