<!-- source: https://developers.wallex.ir/docs/margin-active-markets -->

### مارکت های فعال

در ابتدا برای شروع به معامله در معامله تعهدی ، باید بدانیم که چه بازارهایی در این نوع معامله فعال هستند

```
GET /margin-trade/v1/public/markets
```

### توضیحات Response-Body

```
{
  "symbol": "متشکل از پایه بازار و بازاری که در آن معامله صورت میگیرد",
  "base": "ارز معامله شونده",
  "quote": "ارز قیمت گذار",
  "min_risk_coef": "حداقل نسبت اعتبار",
  "max_risk_coef": "حداکثر نسبت اعتبار",
  "risk_coef_step": "افزایش پله ای نسبت اعتبار",
  "liquidity_margin": "درصد باقی مانده پوزیشن با لیکوییدی",
  "max_age": "ماکزیمم عمر موقعیت"
}
```
