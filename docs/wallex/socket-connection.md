<!-- source: https://developers.wallex.ir/docs/socket-connection -->

### اتصال و عضویت

در این صفحه نحوه‌ی اتصال با **SDK رسمی Centrifugo** توضیح داده شده است. در صورتی که SDK در دسترس ندارید، به صفحه‌ی [اتصال بدون SDK](./socket-raw-protocol.md) مراجعه کنید.

### مراحل کلی

۱. یک client با آدرس وب‌سوکت بسازید.  
۲. در صورتی که به کانال خصوصی نیاز دارید، تابع دریافت توکن را تنظیم کنید.  
۳. جهت هر کانال عمومی یک subscription بسازید و رویدادهای آن را گوش دهید.  
۴. `connect()` را صدا بزنید.

کانال خصوصی مرحله‌ی جداگانه‌ای ندارد و سرور بر اساس توکن، خودش شما را عضو می‌کند. جزئیات در بخش کانال خصوصی آمده است.

### نمونه‌ی کامل (JavaScript)

```
import { Centrifuge } from "centrifuge";

const client = new Centrifuge("wss://api.wallex.ir/connection/websocket");

client.on("connected", (ctx) => console.log("connected", ctx));
client.on("disconnected", (ctx) => console.log("disconnected", ctx.code, ctx.reason));
client.on("error", (ctx) => console.error("error", ctx));

const trades = client.newSubscription("public:BTCTMN@trade");

trades.on("publication", (ctx) => {
  // ctx.data همان بدنه‌ی پیام است
  console.log(ctx.data);
});

trades.subscribe();
client.connect();
```

جهت دریافت داده‌های عمومی نیازی به توکن نمی‌باشد و کاربر لاگین‌نکرده هم می‌تواند متصل شود.

### تاریخچه‌ی کانال‌ها

به جز کانال‌های کندل (`candle:`)، سرور هیچ پیامی را ذخیره نمی‌کند. با عضو شدن **هیچ پیامی** دریافت نمی‌کنید و فقط پیام‌های جدید از آن لحظه به بعد می‌آیند. این موضوع برای عمق بازار هم صادق می‌باشد؛ پاسخ `subscribe` خالی است و اسنپ‌شات فعلی را همراه خود ندارد.

در صورتی که اتصال قطع شود، پیام‌های آن فاصله از دست می‌روند و سرور آن‌ها را دوباره ارسال نمی‌کند. توجه داشته باشید که رویداد `subscribed` فیلد `recovered` ندارد و نباید به آن تکیه کنید.

کانال‌های کندل حداکثر ۱۰ پیام آخر را تا دو دقیقه نگه می‌دارند و اعضای کانال می‌توانند این پیام‌ها را با متد `history` دریافت کنند. جزئیات در [کندل چارت](./socket-candle.md#%D9%87%D9%85%DA%AF%D8%A7%D9%85%D8%B3%D8%A7%D8%B2%DB%8C-api-%D9%88-websocket.md) آمده است.

### کانال خصوصی

کانال خصوصی با کانال‌های عمومی **تفاوت دارد** و کد آن نیز متفاوت نوشته می‌شود.

نام کانال خصوصی داخل توکن، در claim ای به نام `channels`، ارسال می‌شود و سرور به محض برقراری اتصال شما را عضو آن کانال می‌کند. بنابراین:

- توجه داشته باشید که برای این کانال نباید `newSubscription()` بسازید. در صورتی که بسازید و `subscribe()` را صدا بزنید، سرور آن را با خطای `105: already subscribed` رد می‌کند و آن subscription هیچ پیامی دریافت نخواهد کرد.
- پیام‌های این کانال روی رویداد **سطح client** دریافت می‌شوند، نه روی یک subscription. نام کانال در `ctx.channel` قرار دارد و باید خودتان فیلتر کنید.

```
const client = new Centrifuge("wss://api.wallex.ir/connection/websocket", {
  getToken: async () => {
    const res = await fetch("https://api.wallex.ir/v3/auth/token/refresh", {
      method: "POST",
      credentials: "include", // کوکی کاربر باید همراه درخواست برود
    });
    const body = await res.json();
    return body.result.ws_access_token;
  },
});

const privateChannel = `private:user#${userId}`;

client.on("publication", (ctx) => {
  if (ctx.channel === privateChannel) applyUserEvent(ctx.data);
});

client.connect();
```

رویدادهای سطح client که برای کانال خصوصی قابل استفاده می‌باشند عبارت‌اند از `publication`، `subscribed`، `subscribing` و `unsubscribed`. همه‌ی آن‌ها `ctx.channel` دارند و `publication` علاوه بر آن `ctx.data` هم دارد.

جزئیات ساخت توکن در صفحه‌ی [توکن اتصال خصوصی](./socket-token.md) آمده است.

### آزاد کردن کانال‌ها

هر اتصال حداکثر می‌تواند ۶۴ کانال داشته باشد و کانال خصوصی هم در این شمارش محاسبه می‌شود. توجه داشته باشید که هنگام جابه‌جایی بین مارکت‌ها باید کانال‌های قبلی را ببندید، در غیر این صورت به این سقف می‌رسید.

```
function onLeaveMarket() {
  book.unsubscribe();
  book.removeAllListeners();
  trades.unsubscribe();
  trades.removeAllListeners();
}
```

کانال خصوصی را نمی‌توانید با SDK ببندید، زیرا subscription ای برای آن ندارید. جهت خروج از آن باید اتصال را قطع کنید و بدون توکن دوباره وصل شوید. این همان کاری می‌باشد که هنگام logout باید انجام دهید.

### ping و pong

پاسخ دادن به ping سرور به‌صورت خودکار توسط SDK انجام می‌شود. توجه داشته باشید که نباید heartbeat دستی بنویسید.
