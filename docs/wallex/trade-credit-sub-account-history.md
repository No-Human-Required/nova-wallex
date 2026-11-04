<!-- source: https://developers.wallex.ir/docs/trade-credit-sub-account-history -->

### دریافت تاریخچه طرح های اعتبار معاملاتی

برای دریافت تاریخچه های طرح های اعتبار معاملاتی میتوانید از API زیر استفاده کنید.

```
GET /v1/prop/user/packages/history
```

### توضیحات Response-Body

```
{
  "result": [
    {
      "user_id": "شناسه کاربر",
      "client_id": "شناسه حساب فرعی",
      "package_title": "نام پکیج",
      "dark_image_url": "حالت تاریک",
      "light_image_url": "حالت روشن",
      "currency": "ارز پایه",
      "destination_currency": "ارز مقصد",
      "assurance": "وثیقه",
      "loan": "مقدار اعتبار",
      "final_balance": "دارایی نهایی",
      "final_balance_without_transfers": "دارایی نهایی بدون محاسبه انتقال ها",
      "start_balance": "دارایی اولیه",
      "warning_limit": "حد هشدار",
      "liquidity_limit": "حد لیکویید شدن",
      "created_at": "تاریخ فعال کردن پکیج",
      "finished_at": "تاریخ بستن پکیج",
      "expire_at": "تاریخ انقضای پکیج",
      "close_reason": "دلیل بستن پکیج",
      "status": "وضعیت پکیج",
      "expire_days": "تعداد روز  ها تا انقضای پکیج",
      "daily_fee": "کارمزد روزانه",
      "daily_fee_discount": "تخفیف روزانه کارمزد",
      "daily_fee_after_discount": "کارمزد روزانه بعد از کسر تخفیف",
      "final_fee": "کارمزد نهایی",
      "final_fee_discount": "تخفیف نهایی کارمزد",
      "final_fee_after_discount": "کارمزد نهایی بعد از کسر تخفیف",
      "open_days": " تعداد روز های فعال",
      "total_days": "مجموع روز های فعال",
      "applicable_daily_fee": "کارمزد روزانه قابل دریافت ",
      "applicable_daily_fee_discount": "تخفیف قابل کسر از کارمزد روزانه ",
      "applicable_daily_fee_after_discount": "کارمزد روزانه قابل دریافت بعد از تخفیف",
      "profit": "مقدار سود و ضرر",
      "profit_percentage": "درصد سود و ضرر",
      "final_assurance": "وثیقه نهایی",
      "final_payBack": "مبلغ نهایی باز پرداخت"
    }
  ]
}
```
