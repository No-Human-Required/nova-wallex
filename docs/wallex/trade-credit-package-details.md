<!-- source: https://developers.wallex.ir/docs/trade-credit-package-details -->

### دریافت جزیيات پکیج و لیست بازارهای غیر فعال

به منظور بررسی جزییات پکیج میتوانید API زیر را فراخوانی کنید در این API علاوه بر جزئیات پکیج ، لیست بازارهایی را که نمی‌توانید با استفاده از اکانت اعتبار معاملاتی به معامله بپردازید را میتوانید دریافت کنید

```
GET /v1/prop/packages/{id}
```

### توضیحات Path-Variable

به منظور استفاده از این API جهت دریافت جزئیات پکیج باید ID پکیج مورد نظر را به عنوان Path-Variable ارسال کنید. نحوه دریافت ID پکیج ها در [پکیج های اعتبار مهاملاتی والکس](./trade-credit-active-packages.md) آموزش داده شده است.

| Parameter | Example | Data Type | Required | Definition |
| --- | --- | --- | --- | --- |
| id | "10" | Number | true | شناسه یکتای پکیج اعتبار معاملاتی |

### توضیحات Response-Body

```
{
  "result": {
    "detail": {
      "id": "شناسه پکیج",
      "title": "نام پکیج",
      "currency": "ارز پایه",
      "destination_currency": "ارز مقصد",
      "assurance": "وثیقه مورد نیاز برای دریافت اعتبار",
      "loan": "میزان اعتبار دریافتی",
      "warning_limit": "حد هشدار",
      "liquidity_limit": "حد لیکویید شدن",
      "status": "وضعیت پکیج فعال/غیر فعال",
      "expire_days": "تعداد روز منقضی شدن پکیج",
      "dark_image_url": "حالت تاریک",
      "light_image_url": "حالت روشن",
      "daily_fee": "کارمزد روزانه",
      "daily_fee_discount": "تخفیف کارمزد",
      "daily_fee_after_discount": "کارمزد روزانه بعد از کسر تخفیف",
      "final_fee": "کارمزد نهایی",
      "final_fee_discount": "تخفیف کارمزد نهایی",
      "final_fee_after_discount": "کارمزد نهایی بعد از کسر تخفیف",
      "usage_count_step": "تعداد دفعاتی که پکیج فعال شده"
    },
    "unavailableMarkets": [" بازار های غیر فعال"]
  }
}
```
