<!-- source: https://developers.wallex.ir/docs/basic-services-iban-numbers -->

### دریافت شماره های شبای بانکی

جهت دریافت شماره های شبا بانکی اضافه شده حساب کاربری میتوانید از Api زیر اسفاده کنید.

```
GET /v1/account/ibans
```

### توضیحات Response-Body

```
{
  "result": [
    {
      "id": "شناسه یکتا شماره شبا بانکی",
      "withdraw_daily_amount": "مقدار برداشت روزانه",
      "withdraw_available_amount": "مقدار قابل برداشت روزانه",
      "iban": "شماره شبای بانکی",
      "owners": ["صاحب حساب"],
      "bank_name": "نام بانک",
      "status": "وضعیت",
      "is_default": "پیش فرض بودن حساب برای برداشت ها",
      "bank_details": {
        "code": "کد بانک",
        "label": "نام بانک",
        "is_available": "در دسترس بودن"
      }
    }
  ],
  "message": "پیام موفقیت آمیز بودن درخواست",
  "success": "وضعیت موفقیت آمیز بودن",
  "result_info": {
    "page": 1,
    "per_page": 5,
    "count": 5,
    "total_count": 5
  }
}
```
