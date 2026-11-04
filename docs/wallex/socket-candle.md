<!-- source: https://developers.wallex.ir/docs/socket-candle -->

### دریافت به‌روزرسانی کندل‌های نمودار

برای نمایش نمودار، ابتدا تاریخچه‌ی کندل‌ها را مانند قبل از API زیر دریافت کنید و سپس به‌روزرسانی‌های لحظه‌ای را از WebSocket بگیرید:

```
GET /v1/udf/history
```

با برقرار بودن اتصال WebSocket نیازی به polling این API نیست. در صورت قطع اتصال و اتصال مجدد، برای همگام‌سازی مطمئن دوباره تاریخچه را از API دریافت کنید.

این قابلیت فقط روی ورژن ۲ (سنتریفیگو) در دسترس است و روی ورژن ۱ (منسوخ شده) با آدرس `wss://api.wallex.ir/ws` وجود ندارد.

### آدرس اتصال WebSocket

```
wss://api.wallex.ir/connection/websocket
```

این کانال‌ها عمومی هستند و اتصال یا عضویت در آن‌ها به توکن JWT نیاز ندارد. جزئیات ساخت اتصال در صفحه‌ی [اتصال و عضویت](./socket-connection.md) آمده است.

### نام کانال‌ها

به‌جای `<SYMBOL>` نماد بازار را قرار دهید؛ برای مثال `USDTTMN` یا `BTCUSDT`.

| کانال | نوع کندل | مقدار معادل `resolution` در UDF |
| --- | --- | --- |
| `candle:<SYMBOL>@1m` | یک‌دقیقه‌ای | `1` |
| `candle:<SYMBOL>@1h` | یک‌ساعته | `60` |
| `candle:<SYMBOL>@1d` | روزانه | `1D` |

برای مثال:

```
candle:USDTTMN@1m
candle:USDTTMN@1h
candle:USDTTMN@1d
```

نام کانال به بزرگی و کوچکی حروف حساس است و باید دقیقاً از یکی از پسوندهای `1m`، `1h` یا `1d` استفاده شود.

### فرمت پیام

بدنه‌ی `data` دقیقاً از قالب OHLCV پاسخ `udf/history` استفاده می‌کند، با این تفاوت که هر پیام WebSocket فقط یک کندل دارد؛ بنابراین آرایه‌های آن یک عضو دارند.

| فیلد | نوع | توضیح |
| --- | --- | --- |
| `s` | String | وضعیت پاسخ؛ برای به‌روزرسانی معتبر مقدار آن `ok` است. |
| `t` | Array of Unix timestamp | زمان شروع کندل بر حسب ثانیه. |
| `o` | Array of String | قیمت باز شدن کندل. |
| `h` | Array of String | بیشترین قیمت کندل. |
| `l` | Array of String | کمترین قیمت کندل. |
| `c` | Array of String | آخرین قیمت کندل. |
| `v` | Array of String | حجم معامله‌شده‌ی کندل. |

```
{
  "push": {
    "channel": "candle:USDTTMN@1m",
    "pub": {
      "data": {
        "s": "ok",
        "t": [1788873540],
        "c": ["250000.0000000000000000"],
        "o": ["250000.0000000000000000"],
        "h": ["250000.0000000000000000"],
        "l": ["250000.0000000000000000"],
        "v": ["0.0000000000000000"]
      },
      "offset": 2796
    }
  }
}
```

قیمت‌ها و حجم به‌صورت String ارسال می‌شوند؛ برای جلوگیری از خطای اعشاری آن‌ها را مستقیماً با نوع `Number` جاوااسکریپت محاسبه نکنید و از کتابخانه‌ی decimal مناسب استفاده کنید.

### رفتار به‌روزرسانی کندل باز

تا زمانی که بازه‌ی کندل تمام نشده است، چند پیام با مقدار یکسان `t` و مقادیر جدید `o`، `h`، `l`، `c` و `v` دریافت می‌کنید. این پیام‌ها delta نیستند و هر کدام تصویر کامل و جدید همان کندل باز می‌باشند.

کندل‌ها را بر اساس `t` نگه دارید:

- اگر `t` از آخرین کندل بزرگ‌تر بود، یک کندل جدید اضافه کنید.
- اگر `t` با کندل موجود برابر بود، همان کندل را جایگزین کنید.
- ممکن است یک کندل را بیش از یک بار دریافت کنید: از `GET /v1/udf/history`، از متد `history` کانال یا از پیام‌های لحظه‌ای کانال. این اتفاق طبیعی است. در این حالت کندل جدید نسازید و کندلی را که همان `t` را دارد جایگزین کنید.

مقدار `offset` شماره‌ی ترتیبی پیام در همان کانال است و زمان کندل نیست. برای درج یا جایگزینی کندل از `t` استفاده کنید.

### همگام‌سازی API و WebSocket

هر کانال کندل حداکثر ۱۰ پیام آخر را تا دو دقیقه نگه می‌دارد. این history فقط برای پوشش فاصله‌ی کوتاه میان دریافت پاسخ API و رسیدن پیام‌های لحظه‌ای است و جایگزین تاریخچه‌ی اصلی UDF نیست.

ترتیب پیشنهادی:

1. تاریخچه‌ی اولیه را از `GET /v1/udf/history` دریافت و روی نمودار اعمال کنید.
2. در کانال متناسب با resolution عضو شوید و پیام‌های لحظه‌ای را که هنگام همگام‌سازی می‌رسند موقتاً نگه دارید.
3. پس از رویداد `subscribed`، حداکثر ۱۰ پیام آخر کانال را با متد `history` دریافت کنید.
4. پیام‌های history را از قدیمی به جدید و سپس پیام‌های موقت را اعمال کنید.
5. از آن به بعد پیام‌های لحظه‌ای را مستقیم روی نمودار اعمال کنید.
6. پس از reconnect دوباره API را دریافت کنید، چون قطعی طولانی‌تر از دو دقیقه یا بیشتر از ۱۰ پیام با history قابل بازیابی نیست.

با `reverse: true` آخرین پیام‌ها از جدید به قدیم برگردانده می‌شوند؛ بنابراین پیش از اعمال باید ترتیب آرایه را برعکس کنید.

### نمونه‌ی کامل با SDK جاوااسکریپت

در این نمونه `upsertCandle` باید کندل را با کلید timestamp درج یا جایگزین کند.

```
import { Centrifuge } from "centrifuge";

const symbol = "USDTTMN";
const resolution = "1";
const channel = `candle:${symbol}@1m`;

const client = new Centrifuge(
  "wss://api.wallex.ir/connection/websocket"
);

function applyUdfPayload(data) {
  if (data.s !== "ok") return;

  data.t.forEach((timestamp, index) => {
    upsertCandle({
      t: timestamp,
      o: data.o[index],
      h: data.h[index],
      l: data.l[index],
      c: data.c[index],
      v: data.v[index],
    });
  });
}

async function loadUdfHistory() {
  const to = Math.floor(Date.now() / 1000);
  const from = to - 24 * 60 * 60;
  const query = new URLSearchParams({
    symbol,
    resolution,
    from: String(from),
    to: String(to),
  });

  const response = await fetch(`/v1/udf/history?${query}`);
  if (!response.ok) throw new Error(`UDF request failed: ${response.status}`);
  applyUdfPayload(await response.json());
}

// دریافت تاریخچه باید پیش از شروع اتصال WebSocket انجام شود.
await loadUdfHistory();

const buffered = [];
let synchronizing = true;
let subscribedBefore = false;

const sub = client.newSubscription(channel);

sub.on("subscribing", () => {
  synchronizing = true;
});

sub.on("publication", (ctx) => {
  if (synchronizing) {
    buffered.push(ctx.data);
    return;
  }
  applyUdfPayload(ctx.data);
});

sub.on("subscribed", async () => {
  try {
    // پس از reconnect، API دوباره مرجع همگام‌سازی است.
    if (subscribedBefore) await loadUdfHistory();

    const result = await sub.history({
      limit: 10,
      reverse: true,
    });

    result.publications
      .reverse()
      .forEach((publication) => applyUdfPayload(publication.data));

    buffered.splice(0).forEach(applyUdfPayload);
    subscribedBefore = true;
    synchronizing = false;
  } catch (error) {
    console.error("candle synchronization failed", error);

    // در صورت خطای history، API مرجع نهایی است.
    try {
      await loadUdfHistory();
      buffered.splice(0).forEach(applyUdfPayload);
      subscribedBefore = true;
      synchronizing = false;
    } catch (fallbackError) {
      // تا زمان همگام‌سازی موفق، پیام‌ها در buffer باقی می‌مانند.
      console.error("candle fallback failed", fallbackError);
    }
  }
});

sub.subscribe();
client.connect();
```

برای کانال‌های ساعتی و روزانه فقط `channel` و `resolution` را مطابق جدول تغییر دهید. جزئیات متد history در [مستندات رسمی Centrifugo](https://centrifugal.dev/docs/transports/client_api#channel-history-api) آمده است.

### نکته‌های مهم

- history فقط برای اعضای همان کانال کندل قابل دریافت است.
- polling مداوم `udf/history` لازم نیست؛ API در شروع، پس از reconnect یا هنگام خطای همگام‌سازی استفاده می‌شود.
- اگر history در دسترس نبود یا همگام‌سازی ناموفق شد، دوباره `udf/history` را دریافت کنید.
- پاسخ دادن به ping سرور توسط SDK انجام می‌شود و نیازی به heartbeat دستی نیست.
