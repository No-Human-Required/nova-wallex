<!-- source: https://developers.wallex.ir/docs/basic-services-withdraw-toman -->

### ثبت درخواست برداشت تومان

شما میتوانید با استفاده از Api زیر نسبت به ثبت درخواست برداشت تومانی اقدام کنید. توجه داشته باشید Api-Key ارسالی باید مجوز برداشت داشته باشد.

```
POST /v1/account/money-withdrawal
```

### توضیحات Request-Body

توجه داشته باشید که میتوانید شناسه یکتای شماره شبا بانکی خود را از [بخش دریافت شماره شبا بانکی](./basic-services-iban-numbers.md) دریافت کنید

| Parameter | Example | Data Type | Required | Definition |
| --- | --- | --- | --- | --- |
| iban | 12345 | Number | true | شناسه یکتای شماره شبا (ID) |
| value | 98000 | Number | true | مقداری که قصد برداشت دارید |

### توضیحات Response-Body

```
{
  "result": {
    "amount": "مقدار برداشت",
    "fee": "مقدار کارمزد",
    "tracking_code": "کد پیگیری",
    "created_at": "زمان ثبت برداشت",
    "status": "وضعیت برداشت تومان",
    "iban": {
      "id": "شناسه یکتا شماره شب",
      "withdraw_daily_amount": "مقدار برداشت روزانه",
      "withdraw_available_amount": "مقدار قابل برداشت روزانه",
      "iban": "شماره شبا",
      "owners": ["نام صاحب حساب"],
      "bank_name": "نام بانک",
      "status": "وضعیت درخواست",
      "is_default": 0,
      "bank_details": {
        "code": "کد بانک",
        "label": "نام بانک",
        "is_available": "در دسترس بودن"
      }
    },
    "details": [
      {
        "value": "مقدار برداشت تومان",
        "status": "وضعیت برداشت"
      }
    ]
  },
  "message": "درخواست برداشت ثبت شد",
  "success": true
}
```
