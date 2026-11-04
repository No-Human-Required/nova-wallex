<!-- source: https://developers.wallex.ir/docs/socket-raw-protocol -->

### اتصال بدون SDK

در صورتی که برای زبان شما SDK رسمی Centrifugo وجود ندارد، می‌توانید مستقیماً با یک کلاینت وب‌سوکت معمولی به سرور متصل شوید. توجه داشته باشید که در این حالت مدیریت ping/pong و اتصال مجدد بر عهده‌ی خود شما می‌باشد.

تمام نمونه‌های این صفحه، فریم‌های واقعی رد و بدل شده با سرور می‌باشند.

### قواعد ارتباط

- آدرس اتصال: `wss://api.wallex.ir/connection/websocket`
- پیام‌ها **JSON** می‌باشند و در فریم‌های **text** ارسال می‌شوند.
- هر دستور یک `id` عددی یکتا می‌گیرد و پاسخ آن دستور با همان `id` برمی‌گردد.
- پیام‌هایی که `id` ندارند و کلید `push` دارند، داده‌ی کانال می‌باشند.

### گام ۱: دستور connect

اولین دستور بعد از باز شدن سوکت باید `connect` باشد.

جهت کانال‌های عمومی نیازی به توکن نمی‌باشد.

```
{ "id": 1, "connect": {} }
```

پاسخ:

```
{
  "id": 1,
  "connect": {
    "client": "5f194d9b-57fb-45d8-bd2d-6efe83edf0ac",
    "ping": 25,
    "pong": true
  }
}
```

| فیلد | توضیح |
| --- | --- |
| `client` | شناسه‌ی یکتای این اتصال |
| `ping` | فاصله‌ی ping سرور بر حسب ثانیه |
| `pong` | اگر `true` باشد، شما موظف به پاسخ دادن هستید |

جهت کانال خصوصی، توکن را داخل همین دستور ارسال کنید.

```
{ "id": 1, "connect": { "token": "<ws_access_token>" } }
```

در این حالت پاسخ دو مورد بیشتر دارد.

```
{
  "id": 1,
  "connect": {
    "client": "435e348e-6289-4246-a5f7-4033f4bebf6b",
    "expires": true,
    "ttl": 900,
    "subs": { "private:user#42": {} },
    "ping": 25,
    "pong": true
  }
}
```

| فیلد | توضیح |
| --- | --- |
| `expires` و `ttl` | توکن چند ثانیه‌ی دیگر منقضی می‌شود |
| `subs` | کانال‌هایی که سرور شما را عضو آن‌ها کرده است |

توجه داشته باشید که برای کانال خصوصی نباید دستور `subscribe` ارسال کنید. نام کانال خصوصی داخل توکن، در claim ای به نام `channels`، ارسال می‌شود و سرور به محض برقراری اتصال شما را عضو آن می‌کند و این موضوع را در `subs` گزارش می‌دهد. از همان لحظه پیام‌های آن کانال برای شما ارسال می‌شود.

در صورتی که با وجود این یک دستور `subscribe` برای همان کانال ارسال کنید، پاسخ `105: already subscribed` دریافت می‌کنید.

### گام ۲: دستور subscribe

جهت هر کانال باید یک دستور جداگانه ارسال کنید و می‌توانید همه را در یک فریم و پشت سر هم بفرستید.

```
{ "id": 2, "subscribe": { "channel": "public:BTCTMN@trade" } }
{ "id": 3, "subscribe": { "channel": "orderbook:BTCTMN@buyDepth" } }
```

جهت کانال خصوصی چیزی ارسال نکنید، زیرا عضویت آن در پاسخ `connect` انجام شده است.

پاسخ موفق برای **هر** کانالی یک شیء خالی می‌باشد.

```
{ "id": 2, "subscribe": {} }
```

این پاسخ تنها به معنی انجام شدن عضویت می‌باشد و هیچ داده‌ای همراه ندارد. برای کانال‌های `orderbook:` نیز اسنپ‌شات اولیه‌ی عمق بازار ارسال نمی‌شود.

پاسخ خطا نیز با همان `id` برمی‌گردد و بقیه‌ی کانال‌ها را از کار نمی‌اندازد. لیست کدهای خطا در بخش خطاها آمده است.

### گام ۳: دریافت پیام‌ها

پیام‌های کانال با کلید `push` دریافت می‌شوند.

```
{
  "push": {
    "channel": "public:BTCTMN@trade",
    "pub": {
      "data": {
        "isBuyOrder": true,
        "quantity": "0.000243",
        "price": "15791249224",
        "timestamp": "2026-08-25T16:38:23Z"
      }
    }
  }
}
```

بدنه‌ی اصلی پیام در `push.pub.data` و نام کانال در `push.channel` قرار دارد. از آنجا که همه‌ی کانال‌ها روی یک اتصال مشترک می‌باشند، پیام‌ها را با `push.channel` از هم جدا کنید.

به جز پیام‌های کانال‌های کندل (`candle:`)، پیام‌ها شماره‌ی ترتیبی (`offset`) ندارند.

### گام ۴: ping و pong

سرور هر ۲۵ ثانیه یک شیء **خالی** ارسال می‌کند.

```
{}
```

شما باید بلافاصله دقیقاً همان شیء خالی را برگردانید.

```
{}
```

توجه داشته باشید که در صورت پاسخ ندادن ظرف ۸ ثانیه، سرور اتصال را با کد `3012` قطع می‌کند. این تنها کاری می‌باشد که کلاینت بدون SDK حتماً باید خودش انجام دهد.

### گام ۵: اتصال مجدد

به جز کانال‌های کندل (`candle:`)، سرور تاریخچه نگه نمی‌دارد، بنابراین **بازیابی پیام‌های ازدست‌رفته ممکن نیست**. پیام‌هایی که در زمان قطعی منتشر شده‌اند از بین رفته‌اند.

کانال‌های کندل حداکثر ۱۰ پیام آخر را تا دو دقیقه نگه می‌دارند. جزئیات در [کندل چارت](./socket-candle.md#%D9%87%D9%85%DA%AF%D8%A7%D9%85%D8%B3%D8%A7%D8%B2%DB%8C-api-%D9%88-websocket.md) آمده است.

بعد از هر بار قطع شدن اتصال، دستور `connect` را از نو بفرستید و برای کانال‌های عمومی دوباره `subscribe` بفرستید. برای کانال خصوصی توکن تازه بگیرید.

اگر `epoch` و `offset` را داخل دستور `connect` بفرستید، نادیده گرفته می‌شوند و هیچ پیامی برنمی‌گردد. تنها کاربرد کلید `subs` در **پاسخ** `connect` است، که کانال‌های خصوصی داده‌شده توسط توکن را گزارش می‌کند.

### خطاها

خطای مربوط به یک دستور، با همان `id` برمی‌گردد و اتصال قطع نمی‌شود:

```
{ "id": 4, "error": { "code": 102, "message": "unknown channel" } }
```

| کد | معنی | علت رایج در والکس |
| --- | --- | --- |
| `102` | unknown channel | namespace اشتباه است. مثلاً `ticker:all@price` که دیگر وجود ندارد. |
| `103` | permission denied | نام کانال بدون `:` است، یا کانالی را subscribe کرده‌اید که در توکن شما نیست. |
| `105` | already subscribed | قبلاً در همین کانال عضو شده‌اید. رایج‌ترین علت: فرستادن `subscribe` برای کانال خصوصی، که سرور خودش شما را عضو آن کرده است. |
| `106` | limit exceeded | از سقف ۶۴ کانال در هر اتصال عبور کرده‌اید. |
| `107` | bad request | نام کانال با الگوی آن namespace نمی‌خواند. مثلاً `public:BTCTMN@buyDepth`. |
| `108` | not available | متدی مانند `history` را صدا زده‌اید که برای کلاینت فعال نیست. |
| `109` | token expired | توکن منقضی شده است. توکن تازه بگیرید و دوباره connect کنید. |

### کدهای قطع اتصال

اگر اتصال بسته شد، کد close وب‌سوکت را بررسی کنید:

| کد | معنی | اتصال مجدد |
| --- | --- | --- |
| `3005` | اعتبار اتصال تمام شده است. | بله، با توکن تازه |
| `3008` | کلاینت پیام‌ها را به‌اندازه‌ی کافی سریع مصرف نمی‌کند. | بله |
| `3012` | به ping سرور پاسخ نداده‌اید. | بله |
| `3500` | توکن نامعتبر است. | خیر |
| `3501` | فریم ارسالی ساختار درستی ندارد. | خیر |

کدهای `3000` تا `3499` یعنی می‌توانید دوباره وصل شوید. کدهای `3500` به بالا یعنی مشکل از سمت شماست و تلاش مجدد بی‌فایده است.

### نمونه‌ی کامل (Python)

```
import json
import websocket  # pip install websocket-client

URL = "wss://api.wallex.ir/connection/websocket"

CHANNELS = [
    "public:BTCTMN@trade",
    "public:all@price",
    "orderbook:BTCTMN@buyDepth",
]

def on_open(ws):
    ws.send(json.dumps({"id": 1, "connect": {}}))
    for i, ch in enumerate(CHANNELS, start=2):
        ws.send(json.dumps({"id": i, "subscribe": {"channel": ch}}))

def on_message(ws, raw):
    # یک فریم ممکن است چند پیام داشته باشد
    for line in raw.split("\n"):
        if not line:
            continue

        # ping سرور: باید فوراً همان شیء خالی برگردد
        if line == "{}":
            ws.send("{}")
            continue

        msg = json.loads(line)

        if "error" in msg:
            print("error:", msg["error"]["code"], msg["error"]["message"])
            continue

        # داده‌ی کانال
        if "push" in msg:
            pub = msg["push"].get("pub")
            if pub:
                print(msg["push"]["channel"], pub["data"])
            continue

        # پاسخ subscribe یک شیء خالی است و داده‌ای ندارد
        if "subscribe" in msg:
            print("subscribed, id =", msg["id"])

websocket.WebSocketApp(
    URL, on_open=on_open, on_message=on_message
).run_forever()
```

### نمونه‌ی کامل (Go)

```
package main

import (
	"encoding/json"
	"log"
	"strings"

	"github.com/gorilla/websocket"
)

func main() {
	c, _, err := websocket.DefaultDialer.Dial(
		"wss://api.wallex.ir/connection/websocket", nil)
	if err != nil {
		log.Fatal(err)
	}
	defer c.Close()

	c.WriteMessage(websocket.TextMessage, []byte(`{"id":1,"connect":{}}`))
	c.WriteMessage(websocket.TextMessage,
		[]byte(`{"id":2,"subscribe":{"channel":"public:BTCTMN@trade"}}`))

	for {
		_, raw, err := c.ReadMessage()
		if err != nil {
			log.Println("closed:", err)
			return
		}

		for _, line := range strings.Split(string(raw), "\n") {
			if line == "" {
				continue
			}
			// پاسخ به ping سرور
			if line == "{}" {
				c.WriteMessage(websocket.TextMessage, []byte("{}"))
				continue
			}

			var msg struct {
				Push *struct {
					Channel string `json:"channel"`
					Pub     *struct {
						Data json.RawMessage `json:"data"`
					} `json:"pub"`
				} `json:"push"`
				Error *struct {
					Code    int    `json:"code"`
					Message string `json:"message"`
				} `json:"error"`
			}
			json.Unmarshal([]byte(line), &msg)

			switch {
			case msg.Error != nil:
				log.Println("error:", msg.Error.Code, msg.Error.Message)
			case msg.Push != nil && msg.Push.Pub != nil:
				log.Println(msg.Push.Channel, string(msg.Push.Pub.Data))
			}
		}
	}
}
```
