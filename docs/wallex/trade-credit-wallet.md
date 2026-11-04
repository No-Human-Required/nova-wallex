<!-- source: https://developers.wallex.ir/docs/trade-credit-wallet -->

# trade-credit-wallet

### کیف پول اعتبار معاملاتی

برای دریافت اطلاعات کیف پول حساب فرعی اعتبار معاملاتی میتوانید API برای زیر را فراخوانی کنید

#### توضیحات Response-Body

به یاد داشته باشید در Response-Body اطلاعات کیف پول تمامی اکانت های اعتبار معاملاتی در result.subAccounts وجود دارد. آبجکت Result.subaccounts یک Array میباشد که از چندین Object تشکیل شده است. هر Object بیانگر یک اکانت اعتبار معاملاتی میباشد که در هر کدام کلیدی به نام subAccount وجود دارد که subAccount.clientId مطابق با همان  
id اکانت اعتبار معاملاتی خود است که در [زمان ساخت](./trade-credit-activate-sub-account.md) دریافت کردید.

```
{
 "result": {
  "overall": {
   "aggregated": {
    "TMN": {
     "totalAssetWorth": {
      "amount": " مقدار دارایی به تومان",
      "changeAmount": " مقدار تغییرات دارایی به تومان ",
      "changePercentage": " درصد تغییرات دارایی  "
     },
     "propDetail": {
      "assurance": " وثیقه به تومان ",
      "loan": " اعتبار دریافتی به تومان"
     }
    },
    "USDT": {
     "totalAssetWorth": {
      "amount": "مقدار دارایی به تتر",
      "changeAmount": "مقدار تغییرات دارایی به تتر",
      "changePercentage": "درصد تغییرات دارایی"
     },
     "propDetail": {
      "assurance": "وثیقه به تتر",
      "loan": "اعتبار دریافتی به تتر"
     }
    }
   },
   "balances": [
    {
     "currency": "نماد ارز",
     "faName": "نام فارسی ارز",
     "value": " ارزش ارز",
     "locked": "مقدار فریز شده",
     "available": "مقدار در دسترس",
     "assetWorth": "ارزش دارایی",
     "assetWorthChangeAmount": "مقدار تغییرات دارایی",
     "assetWorthChangePercentage": "درصد تغییرات دارایی"
    }
   ]
  },
  "subAccount": {
   "clientId": "شناسه حساب فرعی",
   "title": "عنوان اعتبار معاملاتی",
   "darkAvatarUrl": "حالت تاریک",
   "lightAvatarUrl": "حالت روشن",
   "createdAt": "زمان ساخت اکانت"
  }
 }
}
```
