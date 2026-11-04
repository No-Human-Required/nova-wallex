<!-- source: https://developers.wallex.ir/docs/basic-services-card-numbers -->

### دریافت شماره های کارت بانکی

جهت دریافت شماره های کارت بانکی اضافه شده حساب کاربریتون میتوانید از Api زیر اسفاده کنید.

```
GET /v1/account/card-numbers
```

### توضیحات Response-Body

```
{
  "result": [
    {
      "id": "شناسه یکتا",
      "card_number": "شماره کارت بانکی",
      "owners": ["نام صاحب حساب"],
      "status": "وضعیت ",
      "is_default": "وضعیت پیش فرض بودن شماره کارت بانکی جهت عملیات برداشت)",
      "bank_details": {
        "code": "کد بانک",
        "label": "نام بانک"
      }
    }
  ],
  "message": "پیام موفقیت آمیز بودن درخواست",
  "success": "وضعیت موفقیت آمیز بودن درخواست",
  "result_info": {
    "page": "شمار صفحه",
    "per_page": "تعداد نتایج در هر صفحه",
    "count": "تعداد نتایج در هر صفحه",
    "total_count": "تعداد تمام نتایج"
  }
}
```
