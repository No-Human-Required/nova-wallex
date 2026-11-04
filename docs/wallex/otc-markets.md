<!-- source: https://developers.wallex.ir/docs/otc-markets -->

### مارکت های فعال

در ابتدا برای شروع به معامله آنی ، باید بدانیم که چه بازارهایی در این نوع معامله فعال هستند به منظور این کار شما میتوانید API زیر را فراخوانی کنید.

```
GET /v1/otc/markets
```

### توضیحات Response-Body

```
{
  "result": {
    "USDTTMN": {
      "symbol": "سیمبل",
      "baseAsset": "نام ارز",
      "quoteAsset": "پایه بازار",
      "faName": "نام به فارسی",
      "enName": "نام به انگلیسی",
      "minQty": "حداقل مقدار قابل سفارش به واحد دارایی پایه",
      "minNotional": "حداقل ارزش سفارش",
      "maxNotional": "حداکثر ارزش سفارش",
      "stats": {
        "24h_ch": "تغییرات ۲۴ ساعته",
        "lastPrice": "آخرین قیمت"
      },
      "buyStatus": "وضعیت فعال بودن خرید کوین",
      "sellStatus": "وضعیت فعال بودن فروش کوین",
      "exchangeStatus": "وضعیت فعال بودن در اسپات"
    }
  },
  "message": "عملیات با موفقیت انجام شد",
  "success": true
}
```
