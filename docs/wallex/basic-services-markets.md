<!-- source: https://developers.wallex.ir/docs/basic-services-markets -->

### مارکت های والکس

با استفاده از API زیر میتوانید لیست کاملی از مارکت های فعال در والکس را دریافت کنید. همچنین در هر نوع معامله ی والکس نحوه ی دریافت مارکت های فعال در آن معامله به طور کامل آموزش داده شده است.

```
GET /hector/web/v1/markets
```

### توضیحات Response-Body

```
{
  "result": {
    "markets": [
      {
        "symbol": "بازار معامله",
        "base_asset": "رمزارز معامله شونده",
        "quote_asset": "ارز قیمت گذار",
        "fa_base_asset": "نماد ارز معامله شونده",
        "fa_quote_asset": "نماد ارز قیمت گذار",
        "en_base_asset": "نماد ارز معامله شونده",
        "en_quote_asset": "نماد ارز قیمت گذار",
        "categories": ["number"],
        "price": "قیمت در لحظه فراخوانی ای پی آي",
        "change_24h": "تغییرات 24 ساعته",
        "volume_24h": "حجم 24 ساعته",
        "change_7D": "تغییرات هفت روزه",
        "quote_volume_24h": "حجم تغییرات 24 ساعته",
        "spot_is_new": "آیا به تازگی در بازار اسپات اضافه شده هست",
        "otc_is_new": "آیا به تازگی در بازار خریدفروش آنی اضافه شده هست",
        "is_new": "آیا ارز جدید هست",
        "is_spot": "وضعیت فعال بودن در بازار اسپات",
        "is_otc": "وضعیت فعال بودن در بازار خرید فروش آنی",
        "is_margin": "وضعیت فعال بودن در بازار تعهدی",
        "is_tmn_based": "وضعیت فعال بودن در پایه بازار تومان",
        "is_usdt_based": "وضعیت فعال بودن در پایه بازار تتر",
        "is_zero_fee": "وضعیت رایگان بودن کارمزد در این بازار",
        "leverage_step": "-",
        "max_leverage": "-",
        "created_at": "زمان اضافه شدن رمز ارز",
        "amount_precision": "-",
        "price_precision": "-",
        "flags": ["-"]
      }
    ],
    "message": "The operation was successful",
    "success": true
  }
}
```
