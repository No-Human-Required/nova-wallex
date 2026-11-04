<!-- source: https://developers.wallex.ir/docs/trade-credit-active-packages -->

### پکیج های فعال اعتبار معاملاتی والکس

به منظور ایجاد اکانت اعتبار معاملاتی و استفاده از پکیج های اعتبار معاملاتی والکس ، میتوانید با استفاده از API زیر لیست پکیج های فعال والکس را دریافت کنید.  
حتما توجه داشته باشید که STATUS پکیج ها ACTIVE باشد.

```
GET /v1/prop/packages
```

### توضیحات Response-Body

```
{
  "result": {
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
    "daily_fee_discount": " تخفیف کارمزد",
    "daily_fee_after_discount": "کارمزد روزانه بعد از کسر تخفیف",
    "final_fee": "کارمزد نهایی",
    "final_fee_discount": "تخفیف کارمزد نهایی",
    "final_fee_after_discount": "کارمزد نهایی بعد از کسر تخفیف",
    "usage_count_step": "تعداد دفعاتی که پکیج فعال شده"
  }
}
```
