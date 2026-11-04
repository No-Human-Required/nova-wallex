<!-- source: https://developers.wallex.ir/docs/basic-services-coin-wallets -->

### دریافت آدرس کیف پول رمزارز

جهت دریافت ادرس شبکه کیف پول رمزارز خود میتوانید از Api زیر استفاده کنید

```
GET /v1/account/wallets/{symbol}
```

### توضیحات Response-Body

```
{
  "result": {
    "coin_type": {
      "key": "نماد رمزارز",
      "name": "نام رمزارز",
      "name_en": "نام رمزارز(انگلیسی)",
      "type": "نوع",
      "deposit_availability": "در دتسرس بودن واریز",
      "withdrawal_availability": "در دسترس بودن برداشت",
      "deposit_unavailability_reason": "دلیل عیرفعال بودن واریز",
      "withdrawal_unavailability_reason": "دلیل غیرفعال بودن برداشت"
    },
    "wallets": {
      "نام شبکه": {
        "network": {
          "id": "شناسه یکتا",
          "name": "نام شبکه",
          "deposit_availability": "فعال بودن واریز",
          "withdrawal_availability": "فعال بودن برداشت",
          "deposit_unavailability_reason": "دلیل عیرفعال بودن واریز",
          "withdrawal_unavailability_reason": "دلیل غیرفعال بودن برداشت"
        },
        "address": "آدرس شبکه",
        "memo": "ممو",
        "expire_at": "زمان انقضا",
        "min_confirmation": "حداقل تاییددر شبکه",
        "transaction_fee": "کارمزد تراکنش",
        "min_withdrawal_value": "کمترین مقدار برداشت",
        "min_deposit_value": "کمترین مقدار واریز"
      }
    }
  },
  "message": "پیام موفقیت آمیز بودن درخواست",
  "success": "وضعیت موفقیت آمیز بودن درخواست"
}
```
