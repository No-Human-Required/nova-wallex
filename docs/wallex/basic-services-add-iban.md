<!-- source: https://developers.wallex.ir/docs/basic-services-add-iban -->

### اضافه کردن شماره شبا بانکی

برای اضافه کردن شماره شبای بانکی به حساب خود میتوانید از Api زیر استفاده کنید. توجه داشته باشید شماره شبا اضافه شده باید متعلق به همان شماره ملی باشد که اقدام به ثبت نام کرده اید.

```
POST /v1/account/ibans
```

### توضیحات Request-Body

| Parameter | Example | Data Type | Required | Definition |
| --- | --- | --- | --- | --- |
| iban | 12345738472485748758447384 | Number | true | شماره شبایی که قصد دارید اضافه شود. |

### توضیحات Response-Body

```
{
  "result": {
    "id": "شناسه یکتای شماره شبا",
    "iban": "شماره شبا",
    "owners": ["نام صاحب حساب"],
    "bank_name": "نام بانک",
    "status": "وضعیت استعلام",
    "is_default": 0,
    "bank_details": {
      "code": "کد بانک",
      "label": "نام بانک",
      "is_available": 1
    }
  },
  "message": "پیغام موفقیت آمیز بودن درخواست",
  "success": "وضعیت موفقت آمیز بودن درخواست"
}
```
