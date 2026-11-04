<!-- source: https://developers.wallex.ir/docs/trade-credit-activate-sub-account -->

### فعال کردن پکیج اعتبار معاملاتی

جهت فعال کردن پکیج اعتباری و ساخت اکانت اعتبار معاملاتی ، میتوانید از API زیر استفاده کنید.  
توجه داشته باشید که باید prop_package_id را در Request-Body ارسال کنید.  
این شناسه در Response-Body [پکیج های اعتبار معاملاتی والکس](./trade-credit-active-packages.md) قابل مشاهده میباشد.

```
POST /v1/prop/user/packages
```

### توضیحات Request-Body

برای فراخوانی این API باید اطلاعات زیر را به‌صورت JSON در Request-Body ارسال کنید:

| Parameter | Example | Data Type | Required | Definition |
| --- | --- | --- | --- | --- |
| prop_package_id | "130" | String | true | شناسه یکتای هر پکیج فعال اعتبار معاملاتی والکس |

### توضیحات Response-Body

```
{
  "message": "پیام موفقیت آمیز ساخت اکانت اعتبار معاملاتی",
  "result": {
    "clientId": "شناسه حساب فرعی ",
    "createdAt": "زمان ایجاد اکانت اعتبار معاملاتی",
    "darkAvatarUrl": "حالت تاریک",
    "isActive": "وضعیت فعال بودن اکانت اعتبار معاملاتی",
    "isSuspend": "وضعیت تعلیق پکیج",
    "lightAvatarUrl": "حالت روشن",
    "title": "نام پکیج دریافتی",
    "type": "نوع حساب",
    "userId": "شناسه کاربری "
  },
  "success": "موفقیت آمیز بودن درخواست"
}
```
