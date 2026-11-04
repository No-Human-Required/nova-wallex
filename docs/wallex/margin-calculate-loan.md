<!-- source: https://developers.wallex.ir/docs/margin-calculate-loan -->

### محاسبه میزان حداقل و حداکثر وثیقه

در هر مارکت به نسبت اعتباری که قصد دریافت آن را دارید یک میزان حداقل و حداکثر وثیقه وجود دارد.  
برای محاسبه آن باید API زیر را فراخوانی کنید

```
POST /margin-trade/v1/public/loan
```

### توضیحات Request-Body

برای فراخوانی این API باید اطلاعات زیر را به‌صورت JSON در Request-Body ارسال کنید:

| Parameter | Example | Data Type | Required | Valid Values | Definition |
| --- | --- | --- | --- | --- | --- |
| collateral | "300000" | String | false | — | میزان وثیقه برای ساخت پوزیشن معامله تعهدی |
| market | "BTCUSDT" | String | true | — | بازاری که قصد دارید در آن پوزیشن معامله تعهدی ایجاد نمایید |
| open_price | "80000000" | String | false | — | قیمتی که قصد دارید در آن پوزیشن معامله تعهدی ساخته شود |
| risk_coef | "10" | String | true | — | نسبت اعتباری که قصد دارید دریافت کنید |
| side | long | String | true | long \| short | - |

### توضیحات Response-Body

```
{
  "result": {
    "collateral": {
      "min": "حداقل وثیقه",
      "max": "حداکثر وثیقه"
    },
    "loan": {
      "value": "ارزش وام",
      "currency": "ارز"
    }
  },
  "success": "موفقیت آمیز بودن درخواست"
}
```
