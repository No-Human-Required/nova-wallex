<!-- source: https://developers.wallex.ir/docs/socket-private-channel -->

### رویدادهای خصوصی کاربران

کانال‌های خصوصی WebSocket در والکس به کاربران احراز هویت‌شده اجازه می‌دهند تا تغییرات شخصی مربوط به حساب خود را به‌صورت **لحظه‌ای** دریافت کنند. این رویدادها شامل به‌روزرسانی موجودی، وضعیت سفارش‌ها و جزئیات معاملات می‌باشند.

چهار رویداد وجود دارد: `balanceUpdated`، `orderSaved`، `orderRemoved` و `tradeDetails`. بدنه‌ی این چهار رویداد در هر سه روش زیر یکسان می‌باشد و در بخش رویدادها توضیح داده شده است. آنچه بین سه روش تفاوت دارد، نحوه‌ی عضویت و پوشش بیرونی پیام می‌باشد.

### ورژن ۱ (منسوخ شده)

> **منسوخ شده**
>
> ورژن ۱ (`wss://api.wallex.ir/ws`) منسوخ شده است. این ورژن هنوز کار می‌کند، اما کانال‌های جدید مانند [قیمت منصفانه](./socket-fair-price.md) و [کندل چارت](./socket-candle.md) فقط روی ورژن ۲ (سنتریفیگو) در دسترس هستند.
> 
> برای پیاده‌سازی جدید از ورژن ۲ استفاده کنید. برای انتقال کد فعلی، [راهنمای مهاجرت](./socket-migration.md) را ببینید.

#### آدرس اتصال WebSocket

برای اتصال باید از آدرس زیر استفاده کنید.

```
wss://api.wallex.ir/ws
```

#### فرمت پیام Subscribe

جهت دریافت رویدادهای خصوصی باید پیام خود را با فرمت زیر ارسال کنید.

```
["subscribe", { "channel": "STREAMKEY" }]
```

توجه داشته باشید در هنگام لاگین به والکس در مرحله‌ی آخر یک کلید به نام `stream_key` در پاسخ API دریافت می‌کنید که باید جایگزین STREAMKEY قرار دهید.

رویداد `tradeDetails` روی یک کانال جداگانه ارسال می‌شود، بنابراین باید در آن کانال هم عضو شوید.

```
["subscribe", { "channel": "STREAMKEY@tradeDetails" }]
```

#### نمونه پاسخ دریافتی

پس از ارسال پیام در سوکت، جواب‌هایی که دریافت می‌کنید به‌صورت یک آرایه‌ی دوتایی می‌باشد که عضو اول آن نام کانال و عضو دوم آن بدنه‌ی رویداد است.

```
[
  "STREAMKEY",
  {
    "event": "orderSaved",
    "timestamp": 1748773416414,
    "data": { "symbol": "USDTTMN", "side": "BUY", "status": "NEW", "active": true }
  }
]
```

رویداد `tradeDetails` با نام کانال خودش ارسال می‌شود.

```
[
  "STREAMKEY@tradeDetails",
  {
    "event": "tradeDetails",
    "timestamp": 1782663892725,
    "data": { "symbol": "USDTTMN", "side": "BUY", "price": "172000", "quantity": "2" }
  }
]
```

#### نکته‌ها

- توجه داشته باشید که عضو شدن در این کانال هیچ رویداد قدیمی برای شما ارسال نمی‌کند و فقط رویدادهای جدید از آن لحظه به بعد می‌آیند.
- `tradeDetails` تنها رویدادی می‌باشد که کانال جداگانه دارد و سه رویداد دیگر روی کانال `STREAMKEY` ارسال می‌شوند.
- محدودیت‌ها، پیام‌هایی که داده‌ی کانال نیستند و نحوه‌ی لغو عضویت در [جزئیات ورژن ۱ (منسوخ شده)](./socket-intro.md#%D8%AC%D8%B2%D8%A6%DB%8C%D8%A7%D8%AA-%D9%88%D8%B1%DA%98%D9%86-%DB%B1-%D9%85%D9%86%D8%B3%D9%88%D8%AE-%D8%B4%D8%AF%D9%87.md) آمده است.

### ورژن ۲ (سنتریفیگو) با SDK

#### آدرس اتصال WebSocket

برای اتصال باید از آدرس زیر استفاده کنید.

```
wss://api.wallex.ir/connection/websocket
```

#### نام کانال

به جای `<userId>` شناسه‌ی عددی کاربر قرار می‌گیرد.

```
private:user#<userId>
```

این نام را سرویس توکن والکس داخل توکن قرار می‌دهد و شما فقط جهت تشخیص پیام‌ها به آن نیاز دارید.

#### نمونه کد عضویت

نام کانال خصوصی داخل توکن، در claim ای به نام `channels`، ارسال می‌شود و سرور به محض برقراری اتصال شما را عضو آن می‌کند. بنابراین این کانال یک subscription ندارد و پیام‌های آن روی رویداد **سطح client** دریافت می‌شوند. نام کانال در `ctx.channel` قرار دارد و باید خودتان فیلتر کنید.

```
const client = new Centrifuge("wss://api.wallex.ir/connection/websocket", {
  getToken: async () => {
    const res = await fetch("https://api.wallex.ir/v3/auth/token/refresh", {
      method: "POST",
      credentials: "include", // کوکی کاربر باید همراه درخواست ارسال شود
    });
    const body = await res.json();
    return body.result.ws_access_token;
  },
});

const privateChannel = `private:user#${userId}`;

client.on("publication", (ctx) => {
  if (ctx.channel !== privateChannel) return;

  switch (ctx.data.event) {
    case "balanceUpdated":
      applyBalance(ctx.data.data);
      break;
    case "orderSaved":
      applyOrder(ctx.data.data);
      break;
    case "orderRemoved":
      removeOrder(ctx.data.data);
      break;
    case "tradeDetails":
      applyTrade(ctx.data.data);
      break;
  }
});

client.connect();
```

#### نمونه پاسخ دریافتی

بدنه‌ی رویداد در `ctx.data` قرار دارد.

```
{
  "event": "orderSaved",
  "timestamp": 1748773416414,
  "data": { "symbol": "USDTTMN", "side": "BUY", "status": "NEW", "active": true }
}
```

#### نکته‌ها

- توجه داشته باشید که برای این کانال نباید subscription بسازید. `client.newSubscription("private:user#42")` هیچ پیامی دریافت نمی‌کند و `subscribe()` آن با خطای `105: already subscribed` رد می‌شود.
- هر چهار رویداد روی همین یک کانال ارسال می‌شوند و نوع رویداد از فیلد `event` مشخص می‌شود.
- عضو شدن هیچ رویداد قدیمی برای شما ارسال نمی‌کند و این کانال تاریخچه نگه نمی‌دارد.
- هنگام logout نمی‌توانید فقط از این کانال خارج شوید. باید اتصال را قطع کنید و بدون توکن دوباره وصل شوید.
- نحوه‌ی دریافت توکن در [توکن اتصال خصوصی](./socket-token.md) آمده است.

### ورژن ۲ (سنتریفیگو) بدون SDK

#### آدرس اتصال WebSocket

برای اتصال باید از آدرس زیر استفاده کنید.

```
wss://api.wallex.ir/connection/websocket
```

#### نام کانال

```
private:user#<userId>
```

#### فرمت پیام Subscribe

برای این کانال نیازی به ارسال دستور `subscribe` نمی‌باشد و فقط باید `connect` را ارسال کنید.

```
{ "id": 1, "connect": { "token": "<ws_access_token>" } }
```

پاسخ این دستور، کانالی را که سرور شما را عضو آن کرده است در `subs` گزارش می‌دهد.

```
{ "id": 1, "connect": { "client": "...", "expires": true, "ttl": 900, "subs": { "private:user#42": {} } } }
```

#### نمونه پاسخ دریافتی

پس از برقراری اتصال، جواب‌هایی که دریافت می‌کنید به‌صورت زیر می‌باشد و بدنه‌ی رویداد داخل پوشش `push` قرار دارد.

```
{
  "push": {
    "channel": "private:user#42",
    "pub": {
      "data": {
        "event": "orderSaved",
        "timestamp": 1748773416414,
        "data": { "symbol": "USDTTMN", "side": "BUY", "status": "NEW", "active": true }
      }
    }
  }
}
```

#### نکته‌ها

- توجه داشته باشید که برای این کانال نباید دستور `subscribe` ارسال کنید، در غیر این صورت پاسخ `105: already subscribed` دریافت می‌کنید.
- هر چهار رویداد روی همین یک کانال ارسال می‌شوند و نوع رویداد از فیلد `event` مشخص می‌شود.
- عضو شدن هیچ رویداد قدیمی برای شما ارسال نمی‌کند و این کانال تاریخچه نگه نمی‌دارد.
- پاسخ دادن به ping سرور بر عهده‌ی خود شما می‌باشد. جزئیات در [اتصال بدون SDK](./socket-raw-protocol.md) آمده است.
- نحوه‌ی دریافت توکن در [توکن اتصال خصوصی](./socket-token.md) آمده است.

### رویدادها

بدنه‌ی این چهار رویداد در هر سه روش بالا یکسان می‌باشد.

#### رویداد به‌روزرسانی موجودی کیف پول (balanceUpdated)

پس از هرگونه واریز، برداشت، یا ثبت سفارش و انجام معامله که در پی آن موجودی کیف پول شما به‌روزرسانی می‌شود، این رویداد را دریافت می‌کنید.

| فیلد | نوع | توضیح |
| --- | --- | --- |
| `event` | String | مقدار ثابت `balanceUpdated` |
| `timestamp` | Timestamp | زمان به‌روزرسانی موجودی |
| `asset` | String | ارز به‌روزشده در کیف پول کاربر |
| `value` | String (decimal) | مقدار موجود در کیف پول |
| `locked` | String (decimal) | میزان دارایی فریز شده کاربر |

```
{
  "event": "balanceUpdated",
  "timestamp": 1748773416376,
  "data": {
    "TMN": {
      "asset": "TMN",
      "faName": "تومان",
      "value": "16033085",
      "locked": "2507491"
    }
  }
}
```

#### رویداد ثبت یا به‌روزرسانی سفارش (orderSaved)

پس از ثبت سفارش جدید و یا به‌روزرسانی سفارش‌ها، این رویداد را دریافت می‌کنید.

| فیلد | نوع | توضیح |
| --- | --- | --- |
| `event` | String | مقدار ثابت `orderSaved` |
| `timestamp` | Timestamp | زمان ثبت یا تغییر سفارش |
| `symbol` | String | نام مارکت |
| `side` | String | `BUY` یا `SELL` |
| `price` | String (decimal) | قیمت هر واحد |
| `origQty` | String (decimal) | حجم سفارش |
| `executedQty` | String (decimal) | مقدار معامله‌شده |
| `status` | String | وضعیت سفارش، مانند `NEW` |
| `active` | Boolean | وضعیت فعال بودن سفارش گذاشته شده |
| `clientOrderId` | String | شناسه‌ی سفارش کاربر |

```
{
  "event": "orderSaved",
  "timestamp": 1748773416414,
  "data": {
    "symbol": "USDTTMN",
    "side": "BUY",
    "clientOrderId": "LIMIT-xxxx",
    "price": "82102.0000000000000000",
    "origQty": "10.0000000000000000",
    "executedQty": "0.0000000000000000",
    "status": "NEW",
    "active": true
  }
}
```

#### رویداد حذف سفارش (orderRemoved)

پس از لغو شدن یک سفارش، این رویداد را دریافت می‌کنید. فیلدهای آن مانند رویداد `orderSaved` می‌باشد.

| فیلد | نوع | توضیح |
| --- | --- | --- |
| `event` | String | مقدار ثابت `orderRemoved` |
| `timestamp` | Timestamp | زمان حذف سفارش |
| `symbol` | String | نام مارکت |
| `side` | String | `BUY` یا `SELL` |
| `price` | String (decimal) | قیمت هر واحد |
| `origQty` | String (decimal) | حجم سفارش |
| `executedQty` | String (decimal) | مقدار معامله‌شده پیش از حذف |
| `status` | String | وضعیت سفارش، مانند `CANCELED` |
| `active` | Boolean | برای سفارش حذف‌شده مقدار آن `false` است |
| `clientOrderId` | String | شناسه‌ی سفارش کاربر |

```
{
  "event": "orderRemoved",
  "timestamp": 1748773516414,
  "data": {
    "symbol": "USDTTMN",
    "side": "BUY",
    "clientOrderId": "LIMIT-xxxx",
    "price": "82102.0000000000000000",
    "origQty": "10.0000000000000000",
    "executedQty": "0.0000000000000000",
    "status": "CANCELED",
    "active": false
  }
}
```

#### رویداد جزئیات معامله (tradeDetails)

با هر بار انجام شدن بخشی یا تمام یک سفارش، این رویداد را دریافت می‌کنید که شامل اطلاعات معامله انجام‌شده، کارمزد، قیمت و مقدار معامله می‌باشد.

| فیلد | نوع | توضیح |
| --- | --- | --- |
| `event` | String | مقدار ثابت `tradeDetails` |
| `timestamp` | Timestamp | زمان انجام معامله |
| `symbol` | String | نام مارکت |
| `side` | String | سمت سفارش (`BUY` یا `SELL`) |
| `price` | String (decimal) | قیمت انجام معامله |
| `quantity` | String (decimal) | مقدار معامله انجام‌شده |
| `sum` | String (decimal) | ارزش کل معامله |
| `feeAmount` | String (decimal) | مقدار کارمزد معامله |
| `feeCurrency` | String | ارز کارمزد |
| `isMaker` | Boolean | مشخص می‌کند معامله از نوع Maker بوده یا Taker |
| `clientOrderID` | String | شناسه سفارش کاربر |

```
{
  "event": "tradeDetails",
  "timestamp": 1782663892725,
  "data": {
    "clientOrderID": "LIMIT-e441b494-730d-11f1-8a2a-9afca993d5d3",
    "feeAmount": "0.003",
    "feeCurrency": "USDT",
    "isMaker": false,
    "price": "172000",
    "quantity": "2",
    "side": "BUY",
    "sum": "344000",
    "symbol": "USDTTMN"
  }
}
```
