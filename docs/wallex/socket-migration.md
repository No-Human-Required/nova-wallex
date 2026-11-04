<!-- source: https://developers.wallex.ir/docs/socket-migration -->

### راهنمای مهاجرت

در صورتی که از ورژن ۱ (منسوخ شده) استفاده می‌کنید، جدول زیر معادل هر بخش را نشان می‌دهد.

| مورد | ورژن ۱ (منسوخ شده) | ورژن ۲ (سنتریفیگو) |
| --- | --- | --- |
| آدرس اتصال | `wss://api.wallex.ir/ws` | `wss://api.wallex.ir/connection/websocket` |
| اتصال | `["subscribe", { "channel": "BTCTMN@trade" }]` | `{ "id": 2, "subscribe": { "channel": "public:BTCTMN@trade" } }` |
| قالب پیام دریافتی | `["BTCTMN@trade", { "isBuyOrder": true, "quantity": "0.000243", "price": "15791249224", "timestamp": "2026-08-25T16:38:23Z" }]` | `{ "push": { "channel": "public:BTCTMN@trade", "pub": { "data": { "isBuyOrder": true, "quantity": "0.000243", "price": "15791249224", "timestamp": "2026-08-25T16:38:23Z" } } } }` |
| معاملات | `BTCTMN@trade` | `public:BTCTMN@trade` |
| قیمت همه بازارها | `all@price` | `public:all@price` |
| عمق خرید | `BTCTMN@buyDepth` | `orderbook:BTCTMN@buyDepth` |
| عمق فروش | `BTCTMN@sellDepth` | `orderbook:BTCTMN@sellDepth` |
| کانال خصوصی | `<stream_key>` | `private:user#<userId>` |
| جزئیات معامله | کانال جدا: `<stream_key>@tradeDetails` | همان کانال خصوصی، با فیلد `event` |
| ping/pong | فریم‌های استاندارد ping/pong وب‌سوکت. مرورگرها و بیشتر کتابخانه‌ها خودکار پاسخ می‌دهند. | شیء خالی `{}` |

مهم‌ترین تفاوت‌ها هنگام مهاجرت:

۱. **هر نام کانال باید یک namespace داشته باشد.** نام کانال بدون `:` پذیرفته نمی‌شود.  
۲. **هر دستور یک `id` می‌گیرد** و پاسخ با همان `id` برمی‌گردد.  
۳. **بدنه‌ی پیام داخل `push.pub.data` قرار دارد**، نه عضو دوم یک آرایه.  
۴. **کانال خصوصی به توکن JWT نیاز دارد**، نه به `stream_key`. برای این کانال دستور `subscribe` هم ارسال نمی‌کنید و سرور بر اساس توکن، خودش شما را عضو می‌کند. جزئیات در [توکن اتصال خصوصی](./socket-token.md) آمده است.
