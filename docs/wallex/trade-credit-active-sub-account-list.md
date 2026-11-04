<!-- source: https://developers.wallex.ir/docs/trade-credit-active-sub-account-list -->

### لیست حساب های اعتبار معاملاتی

برای دریافت لیست حساب های فرعی API زیر را فراخوانی می کنیم

```
GET /sub-accounts
```

### توضیحات Response-Body

```
{
  "result": {
    "userId": "شناسه کاربری",
    "title": " نام پکیج",
    "darkAvatarUrl": "حالت تاریک",
    "lightAvatarUrl": "حالت روشن",
    "clientId": "شناسه حساب اعتبار معاملاتی",
    "isActive": "وضعیت فعال بودن",
    "type": "نوع حساب",
    "createdAt": "زمان ساخت حساب اعتبار معاملاتی",
    "isSuspend": " وضعیت معلق بودن"
  }
}
```
