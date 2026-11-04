<!-- source: https://developers.wallex.ir/docs/generated/prop-packages-list -->

# Prop Packages List

`GET /v1/prop/packages`

**Base URL:** `https://api.wallex.ir`

# GET v1/prop/packages

This endpoint retrieves a list of existing prop packages.

## Headers

This request does not require any custom header.

## Request Body Parameters

This request does not require a request body.

## Query Parameters

This request does not require any query parameters.

## Response

The response for this request is a JSON object with the following properties:

- `result` (array\[object\])

    - `id` (number)

    - `title` (string)

    - `currency` (string)

    - `destination_currency` (string|null)

    - `assurance` (string)

    - `loan` (string)

    - `warning_limit` (string)

    - `liquidity_limit` (string)

    - `status` (string)

    - `expire_days` (number)

    - `dark_image_url` (string)

    - `light_image_url` (string)

    - `daily_fee` (string)

    - `daily_fee_discount` (string)

    - `daily_fee_after_discount` (string)

    - `final_fee` (string)

    - `final_fee_discount` (string)

    - `final_fee_after_discount` (string)

- `message` (string)
- `success` (boolean)

## Example Response

``` json
{
    "result": [
        {
            "id": 81,
            "title": "طرح ۱۷",
            "currency": "TMN",
            "destination_currency": null,
            "assurance": "20000000",
            "loan": "200000000",
            "warning_limit": "250000000",
            "liquidity_limit": "240000000",
            "status": "INACTIVE",
            "expire_days": 30,
            "dark_image_url": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
            "light_image_url": "https://s3.thr1.sotoon.ir/phinix-public-staging/packages/clHyoeip3vrFmJvxRbjMP42h8PYDSWcKeo0zkQZO.jpg",
            "daily_fee": "300000",
            "daily_fee_discount": "0",
            "daily_fee_after_discount": "300000",
            "final_fee": "9000000",
            "final_fee_discount": "0",
            "final_fee_after_discount": "9000000"
        },
    ],
    "message": "عملیات با موفقیت انجام شد",
    "success": true
}

 ```

**Tags:** trade-credit

## Authentication

- `x-api-key` — apiKey in header `x-api-key`

## Parameters

| Name | In | Type | Required | Description |
| --- | --- | --- | --- | --- |
| `` | query | string |  |  |

## Responses

### 200 — 200

Content-Type: `application/json`

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `message` | string |  |  (example: `"عملیات با موفقیت انجام شد"`) |
| `result` | array<object> |  |  (example: `[{"assurance": "60000000", "currency": "TMN", "daily_fee": "600000", "daily_fee_after_discount": "600000", "daily_fee_discount": "0", "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/QrOWJudTqCA4BxKlRZ99vFcnkUG5SEWNBoK5ayu2.png", "destination_currency": null, "expire_days": 30, "final_fee": "18000000", "final_fee_after_discount": "18000000", "final_fee_discount": "0", "id": 147, "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/ceY4TTn6yQXvmUHZvy2g3e5B8zt6sGsI2XAQuhFl.png", "liquidity_limit": "624000000", "loan": "600000000", "status": "INACTIVE", "title": "600 میلیون اعتبار معاملاتی", "warning_limit": "642000000"}, {"assurance": "50000000", "currency": "TMN", "daily_fee": "500000", "daily_fee_after_discount": "500000", "daily_fee_discount": "0", "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/eK5KaiA7xiyOIppyYHvcRCQhgK2d1SKGvoID2sie.png", "destination_currency": null, "expire_days": 30, "final_fee": "15000000", "final_fee_after_discount": "15000000", "final_fee_discount": "0", "id": 119, "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/7ztIwZQYevSfKaTtM2jQrPxPncRBSnRBaLXwTaVf.png", "liquidity_limit": "520000000", "loan": "500000000", "status": "ACTIVE", "title": "500 میلیون اعتبار معاملاتی", "warning_limit": "535000000"}, {"assurance": "100000", "currency": "TMN", "daily_fee": "3000", "daily_fee_after_discount": "3000", "daily_fee_discount": "0", "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/AaR7zhqWFsU8o74wMlyyEKSNkemyAqVjagXp2jw7.png", "destination_currency": null, "expire_days": 30, "final_fee": "90000", "final_fee_after_discount": "90000", "final_fee_discount": "0", "id": 137, "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/GiwJXCCqKKwUl9smvOTnflRzcdM2v58CP4vJNYFH.png", "liquidity_limit": "3060000", "loan": "3000000", "status": "ACTIVE", "title": "3 میلیون اعتبار معاملاتی", "warning_limit": "3090000"}, {"assurance": "100000", "currency": "TMN", "daily_fee": "1500", "daily_fee_after_discount": "1500", "daily_fee_discount": "0", "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/skQNe8de3Grf3PNHT9wAj7e15B5dnkzA9n9jgGRO.png", "destination_currency": null, "expire_days": 30, "final_fee": "45000", "final_fee_after_discount": "45000", "final_fee_discount": "0", "id": 134, "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/SRq7winv8epgS90fMjYfLHiqWKmV1OxPwuf40NmB.png", "liquidity_limit": "1545000", "loan": "1500000", "status": "INACTIVE", "title": "1.5 میلیون اعتبار معاملاتی", "warning_limit": "1560000"}, {"assurance": "4000000", "currency": "TMN", "daily_fee": "60000", "daily_fee_after_discount": "60000", "daily_fee_discount": "0", "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/J7aaP2hjQcMKPDNMc3Qq7ETTMvc97QK2LESmtb7Y.png", "destination_currency": null, "expire_days": 30, "final_fee": "1800000", "final_fee_after_discount": "1800000", "final_fee_discount": "0", "id": 128, "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/XVbSK2cLT3uiycs9MrzgVWSJC9eW2YYSuaMk02fl.png", "liquidity_limit": "61800000", "loan": "60000000", "status": "ACTIVE", "title": "60 میلیون اعتبار معاملاتی", "warning_limit": "62700000"}, {"assurance": "10000000", "currency": "TMN", "daily_fee": "100000", "daily_fee_after_discount": "100000", "daily_fee_discount": "0", "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/smCGk2fMduT399ruI8uzF8pbNvITLy9gyrq3eI3o.png", "destination_currency": null, "expire_days": 30, "final_fee": "3000000", "final_fee_after_discount": "3000000", "final_fee_discount": "0", "id": 107, "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/8aju9yCJhGqOlIn2RsWkpHUJmZPz9MWIQSvLwotA.png", "liquidity_limit": "104000000", "loan": "100000000", "status": "ACTIVE", "title": "100 میلیون اعتبار معاملاتی", "warning_limit": "107000000"}, {"assurance": "30000000", "currency": "TMN", "daily_fee": "300000", "daily_fee_after_discount": "300000", "daily_fee_discount": "0", "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/vCdyBJxZsca6MwvrROO3OjLsInhIhl0nB67Szf3i.png", "destination_currency": null, "expire_days": 30, "final_fee": "9000000", "final_fee_after_discount": "9000000", "final_fee_discount": "0", "id": 116, "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/TZjvxzGD4JVGt4EEjaSsT5KxLb3F4GVXSh2w2qIu.png", "liquidity_limit": "312000000", "loan": "300000000", "status": "ACTIVE", "title": "300 میلیون اعتبار معاملاتی", "warning_limit": "321000000"}, {"assurance": "200", "currency": "USDT", "daily_fee": "0.5", "daily_fee_after_discount": "0.5", "daily_fee_discount": "0", "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/cCM6nyg1K9akqVnIGQVZ3elO9xd1eG55qexYlCgf.png", "destination_currency": null, "expire_days": 30, "final_fee": "15", "final_fee_after_discount": "15", "final_fee_discount": "0", "id": 146, "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/S81UZpQ9QsWjnxW47rrVww1tiwor18nwG2j6NXb6.png", "liquidity_limit": "1040", "loan": "1000", "status": "ACTIVE", "title": "1000 تتر اعتبار معاملاتی", "warning_limit": "1070"}, {"assurance": "50", "currency": "USDT", "daily_fee": "0.2", "daily_fee_after_discount": "0.2", "daily_fee_discount": "0", "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/dENZiRwyoSLtSuRgspmIIIBfQCADeysjFsTS6Fcz.png", "destination_currency": null, "expire_days": 30, "final_fee": "6", "final_fee_after_discount": "6", "final_fee_discount": "0", "id": 143, "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/Y6gfyqFrnngQJDFmw3fI9CJ0x3MHKGuLhwRYuPu6.png", "liquidity_limit": "416", "loan": "400", "status": "ACTIVE", "title": "400 تتر اعتبار معاملاتی", "warning_limit": "428"}, {"assurance": "2000000", "currency": "TMN", "daily_fee": "30000", "daily_fee_after_discount": "30000", "daily_fee_discount": "0", "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/PCehq12IOqO6u2TE0apKRr75sTTdrYu8RPsr4fHU.png", "destination_currency": null, "expire_days": 30, "final_fee": "900000", "final_fee_after_discount": "900000", "final_fee_discount": "0", "id": 131, "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/MuIyDfbsdCTMFcF9bSyWQNEaAkVLPdCX93PR27tv.png", "liquidity_limit": "30900000", "loan": "30000000", "status": "ACTIVE", "title": "۳۰ میلیون اعتبار معاملاتی", "warning_limit": "31200000"}, {"assurance": "200", "currency": "USDT", "daily_fee": "1", "daily_fee_after_discount": "1", "daily_fee_discount": "0", "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/sFhEQtqD2k38ygKDMhydTFROej0VRcnE48pB2iP9.png", "destination_currency": null, "expire_days": 30, "final_fee": "30", "final_fee_after_discount": "30", "final_fee_discount": "0", "id": 140, "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/6qSIvatJ9EYAvuEfP2k7f1eJiwh8HuIyy4HxZNao.png", "liquidity_limit": "2080", "loan": "2000", "status": "ACTIVE", "title": "۲۰۰۰ تتر اعتبار معاملاتی", "warning_limit": "2140"}, {"assurance": "100", "currency": "USDT", "daily_fee": "0.5", "daily_fee_after_discount": "0.5", "daily_fee_discount": "0", "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/6TBRjooe1smhFFVvctn5mXWQyYgGQHnQ4KP6kGzC.png", "destination_currency": null, "expire_days": 30, "final_fee": "15", "final_fee_after_discount": "15", "final_fee_discount": "0", "id": 122, "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/CZ5WKgLjqobOjI0v5ssITkFFgbNT6PB4UAuIqbdo.png", "liquidity_limit": "1040", "loan": "1000", "status": "ACTIVE", "title": "1000 تتر اعتبار معاملاتی", "warning_limit": "1070"}, {"assurance": "20000000", "currency": "TMN", "daily_fee": "200000", "daily_fee_after_discount": "200000", "daily_fee_discount": "0", "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/NDHttjNUufen1eGvqy15KQf14YmkJeCjZpjIjS7R.svg", "destination_currency": null, "expire_days": 30, "final_fee": "6000000", "final_fee_after_discount": "6000000", "final_fee_discount": "0", "id": 113, "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/AfCYnScOe5cQ148IcTnHsVCNvqLmwP626dazZUDB.svg", "liquidity_limit": "208000000", "loan": "200000000", "status": "ACTIVE", "title": "200 میلیون اعتبار معاملاتی", "warning_limit": "214000000"}, {"assurance": "1000000", "currency": "TMN", "daily_fee": "10000", "daily_fee_after_discount": "10000", "daily_fee_discount": "0", "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/1rX2EiHtSN0pm8wY5IeeD0PVFfPV8YtARYhS5K1u.png", "destination_currency": null, "expire_days": 30, "final_fee": "300000", "final_fee_after_discount": "300000", "final_fee_discount": "0", "id": 101, "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/4cyZKkkKacBAEOMYrBqCmKdTlL4RWey1anAEjwQk.png", "liquidity_limit": "10400000", "loan": "10000000", "status": "ACTIVE", "title": "10 میلیون اعتبار معاملاتی", "warning_limit": "10700000"}, {"assurance": "5000000", "currency": "TMN", "daily_fee": "25000", "daily_fee_after_discount": "25000", "daily_fee_discount": "0", "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/dsKIHlBwaDFYi1ZDuZFkpEmdEROoksIHJoumAUYv.png", "destination_currency": null, "expire_days": 30, "final_fee": "750000", "final_fee_after_discount": "750000", "final_fee_discount": "0", "id": 110, "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/iIDmZchey8NNFvrj4kqSz0uqFNe7ccGwpGVDKAIz.png", "liquidity_limit": "26000000", "loan": "25000000", "status": "ACTIVE", "title": "25 میلیون اعتبار معاملاتی", "warning_limit": "26750000"}, {"assurance": "10000000", "currency": "TMN", "daily_fee": "50000", "daily_fee_after_discount": "50000", "daily_fee_discount": "0", "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/Xa7dc76ouezN2vAtmi1yFW4ZNADyhQfJTBycq2Nm.png", "destination_currency": null, "expire_days": 30, "final_fee": "1500000", "final_fee_after_discount": "1500000", "final_fee_discount": "0", "id": 79, "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/PUqIeYEOLP9WOLTZCIxpU4bL5NRF6lwDDnwd7tCE.png", "liquidity_limit": "52000000", "loan": "50000000", "status": "ACTIVE", "title": "50 میلیون اعتبار معاملاتی", "warning_limit": "53500000"}, {"assurance": "20000000", "currency": "TMN", "daily_fee": "100000", "daily_fee_after_discount": "100000", "daily_fee_discount": "0", "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/KOi8SROWgHh4UDRD3p4VHdPlaBJRVgjic6ry94Yb.png", "destination_currency": null, "expire_days": 30, "final_fee": "3000000", "final_fee_after_discount": "3000000", "final_fee_discount": "0", "id": 104, "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/9Hu9vt5HFlUxNKxKLmd6oqeAoiiMtqIWb9MCiRom.png", "liquidity_limit": "104000000", "loan": "100000000", "status": "ACTIVE", "title": "100 میلیون اعتبار معاملاتی", "warning_limit": "107000000"}, {"assurance": "10000000", "currency": "TMN", "daily_fee": "40000", "daily_fee_after_discount": "40000", "daily_fee_discount": "0", "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/qojEXt6QjlMdO2YprMFIV1x2TCjWCtawrWBu0Jvy.png", "destination_currency": null, "expire_days": 30, "final_fee": "1200000", "final_fee_after_discount": "1200000", "final_fee_discount": "0", "id": 76, "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/KaLDBDgyIROq2LimeKpG5pjnehswRCdpln5cqtcV.png", "liquidity_limit": "41600000", "loan": "40000000", "status": "ACTIVE", "title": "40 میلیون اعتبار معاملاتی", "warning_limit": "42800000"}, {"assurance": "100000000", "currency": "TMN", "daily_fee": "300000", "daily_fee_after_discount": "300000", "daily_fee_discount": "0", "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/Rn7TVSIEzfZFyc5vuheqKFoNCkuouJFYxJlNkOAF.png", "destination_currency": null, "expire_days": 30, "final_fee": "9000000", "final_fee_after_discount": "9000000", "final_fee_discount": "0", "id": 97, "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/EOmEhwaJKwnhnVhjg7OeGKQYh5duOS5gGARpwGUX.png", "liquidity_limit": "312000000", "loan": "300000000", "status": "ACTIVE", "title": "300 میلیون اعتبار معاملاتی", "warning_limit": "321000000"}, {"assurance": "10000000", "currency": "TMN", "daily_fee": "30000", "daily_fee_after_discount": "30000", "daily_fee_discount": "0", "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/mDBahzwIu2UdDZ37Dy56hU2bI6V7DAKZltVGK1xk.png", "destination_currency": null, "expire_days": 30, "final_fee": "900000", "final_fee_after_discount": "900000", "final_fee_discount": "0", "id": 73, "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/F2doDvaz24YhvTdhWMVpBECtvQgvz7R11qQTypHe.png", "liquidity_limit": "32136000", "loan": "30000000", "status": "INACTIVE", "title": "30 میلیون اعتبار معاملاتی", "warning_limit": "34715000"}, {"assurance": "50000000", "currency": "TMN", "daily_fee": "150000", "daily_fee_after_discount": "150000", "daily_fee_discount": "0", "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/1b4UBGRgGfTXLsOmkKWxxrtYXrAuB9cLQblRcULx.png", "destination_currency": null, "expire_days": 30, "final_fee": "4500000", "final_fee_after_discount": "4500000", "final_fee_discount": "0", "id": 91, "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/jdU7JWXampXUCezLgN0JD6Bga3mYMBNAEJaFhEhu.png", "liquidity_limit": "156000000", "loan": "150000000", "status": "ACTIVE", "title": "150 میلیون اعتبار معاملاتی", "warning_limit": "160500000"}, {"assurance": "20000000", "currency": "TMN", "daily_fee": "60000", "daily_fee_after_discount": "60000", "daily_fee_discount": "0", "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/oreeZUbvdF8iwORrpV7RXCbfiCRShqCgK6R5syxO.png", "destination_currency": null, "expire_days": 30, "final_fee": "1800000", "final_fee_after_discount": "1800000", "final_fee_discount": "0", "id": 82, "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/aR8eaa37bYiH6FxF7wMnp5kGzVrK4Yr07C2bzeZz.png", "liquidity_limit": "62400000", "loan": "60000000", "status": "INACTIVE", "title": "60 میلیون اعتبار معاملاتی", "warning_limit": "64200000"}]`) |
| `result[].assurance` | string |  |  (example: `"60000000"`) |
| `result[].currency` | string |  |  (example: `"TMN"`) |
| `result[].daily_fee` | string |  |  (example: `"600000"`) |
| `result[].daily_fee_after_discount` | string |  |  (example: `"600000"`) |
| `result[].daily_fee_discount` | string |  |  (example: `"0"`) |
| `result[].dark_image_url` | string |  |  (example: `"https://s3.thr1.sotoon.ir/wallex-public/packages/QrOWJudTqCA4BxKlRZ99vFcnkUG5SEWNBoK5ayu2.png"`) |
| `result[].destination_currency` | any |  |  |
| `result[].expire_days` | number |  |  (example: `30`) |
| `result[].final_fee` | string |  |  (example: `"18000000"`) |
| `result[].final_fee_after_discount` | string |  |  (example: `"18000000"`) |
| `result[].final_fee_discount` | string |  |  (example: `"0"`) |
| `result[].id` | number |  |  (example: `147`) |
| `result[].light_image_url` | string |  |  (example: `"https://s3.thr1.sotoon.ir/wallex-public/packages/ceY4TTn6yQXvmUHZvy2g3e5B8zt6sGsI2XAQuhFl.png"`) |
| `result[].liquidity_limit` | string |  |  (example: `"624000000"`) |
| `result[].loan` | string |  |  (example: `"600000000"`) |
| `result[].status` | string |  |  (example: `"INACTIVE"`) |
| `result[].title` | string |  |  (example: `"600 میلیون اعتبار معاملاتی"`) |
| `result[].warning_limit` | string |  |  (example: `"642000000"`) |
| `success` | boolean |  |  (example: `true`) |

<details><summary>Example / shape</summary>

```json
{
  "message": "عملیات با موفقیت انجام شد",
  "result": [
    {
      "assurance": "60000000",
      "currency": "TMN",
      "daily_fee": "600000",
      "daily_fee_after_discount": "600000",
      "daily_fee_discount": "0",
      "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/QrOWJudTqCA4BxKlRZ99vFcnkUG5SEWNBoK5ayu2.png",
      "destination_currency": null,
      "expire_days": 30,
      "final_fee": "18000000",
      "final_fee_after_discount": "18000000",
      "final_fee_discount": "0",
      "id": 147,
      "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/ceY4TTn6yQXvmUHZvy2g3e5B8zt6sGsI2XAQuhFl.png",
      "liquidity_limit": "624000000",
      "loan": "600000000",
      "status": "INACTIVE",
      "title": "600 میلیون اعتبار معاملاتی",
      "warning_limit": "642000000"
    },
    {
      "assurance": "50000000",
      "currency": "TMN",
      "daily_fee": "500000",
      "daily_fee_after_discount": "500000",
      "daily_fee_discount": "0",
      "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/eK5KaiA7xiyOIppyYHvcRCQhgK2d1SKGvoID2sie.png",
      "destination_currency": null,
      "expire_days": 30,
      "final_fee": "15000000",
      "final_fee_after_discount": "15000000",
      "final_fee_discount": "0",
      "id": 119,
      "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/7ztIwZQYevSfKaTtM2jQrPxPncRBSnRBaLXwTaVf.png",
      "liquidity_limit": "520000000",
      "loan": "500000000",
      "status": "ACTIVE",
      "title": "500 میلیون اعتبار معاملاتی",
      "warning_limit": "535000000"
    },
    {
      "assurance": "100000",
      "currency": "TMN",
      "daily_fee": "3000",
      "daily_fee_after_discount": "3000",
      "daily_fee_discount": "0",
      "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/AaR7zhqWFsU8o74wMlyyEKSNkemyAqVjagXp2jw7.png",
      "destination_currency": null,
      "expire_days": 30,
      "final_fee": "90000",
      "final_fee_after_discount": "90000",
      "final_fee_discount": "0",
      "id": 137,
      "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/GiwJXCCqKKwUl9smvOTnflRzcdM2v58CP4vJNYFH.png",
      "liquidity_limit": "3060000",
      "loan": "3000000",
      "status": "ACTIVE",
      "title": "3 میلیون اعتبار معاملاتی",
      "warning_limit": "3090000"
    },
    {
      "assurance": "100000",
      "currency": "TMN",
      "daily_fee": "1500",
      "daily_fee_after_discount": "1500",
      "daily_fee_discount": "0",
      "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/skQNe8de3Grf3PNHT9wAj7e15B5dnkzA9n9jgGRO.png",
      "destination_currency": null,
      "expire_days": 30,
      "final_fee": "45000",
      "final_fee_after_discount": "45000",
      "final_fee_discount": "0",
      "id": 134,
      "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/SRq7winv8epgS90fMjYfLHiqWKmV1OxPwuf40NmB.png",
      "liquidity_limit": "1545000",
      "loan": "1500000",
      "status": "INACTIVE",
      "title": "1.5 میلیون اعتبار معاملاتی",
      "warning_limit": "1560000"
    },
    {
      "assurance": "4000000",
      "currency": "TMN",
      "daily_fee": "60000",
      "daily_fee_after_discount": "60000",
      "daily_fee_discount": "0",
      "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/J7aaP2hjQcMKPDNMc3Qq7ETTMvc97QK2LESmtb7Y.png",
      "destination_currency": null,
      "expire_days": 30,
      "final_fee": "1800000",
      "final_fee_after_discount": "1800000",
      "final_fee_discount": "0",
      "id": 128,
      "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/XVbSK2cLT3uiycs9MrzgVWSJC9eW2YYSuaMk02fl.png",
      "liquidity_limit": "61800000",
      "loan": "60000000",
      "status": "ACTIVE",
      "title": "60 میلیون اعتبار معاملاتی",
      "warning_limit": "62700000"
    },
    {
      "assurance": "10000000",
      "currency": "TMN",
      "daily_fee": "100000",
      "daily_fee_after_discount": "100000",
      "daily_fee_discount": "0",
      "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/smCGk2fMduT399ruI8uzF8pbNvITLy9gyrq3eI3o.png",
      "destination_currency": null,
      "expire_days": 30,
      "final_fee": "3000000",
      "final_fee_after_discount": "3000000",
      "final_fee_discount": "0",
      "id": 107,
      "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/8aju9yCJhGqOlIn2RsWkpHUJmZPz9MWIQSvLwotA.png",
      "liquidity_limit": "104000000",
      "loan": "100000000",
      "status": "ACTIVE",
      "title": "100 میلیون اعتبار معاملاتی",
      "warning_limit": "107000000"
    },
    {
      "assurance": "30000000",
      "currency": "TMN",
      "daily_fee": "300000",
      "daily_fee_after_discount": "300000",
      "daily_fee_discount": "0",
      "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/vCdyBJxZsca6MwvrROO3OjLsInhIhl0nB67Szf3i.png",
      "destination_currency": null,
      "expire_days": 30,
      "final_fee": "9000000",
      "final_fee_after_discount": "9000000",
      "final_fee_discount": "0",
      "id": 116,
      "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/TZjvxzGD4JVGt4EEjaSsT5KxLb3F4GVXSh2w2qIu.png",
      "liquidity_limit": "312000000",
      "loan": "300000000",
      "status": "ACTIVE",
      "title": "300 میلیون اعتبار معاملاتی",
      "warning_limit": "321000000"
    },
    {
      "assurance": "200",
      "currency": "USDT",
      "daily_fee": "0.5",
      "daily_fee_after_discount": "0.5",
      "daily_fee_discount": "0",
      "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/cCM6nyg1K9akqVnIGQVZ3elO9xd1eG55qexYlCgf.png",
      "destination_currency": null,
      "expire_days": 30,
      "final_fee": "15",
      "final_fee_after_discount": "15",
      "final_fee_discount": "0",
      "id": 146,
      "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/S81UZpQ9QsWjnxW47rrVww1tiwor18nwG2j6NXb6.png",
      "liquidity_limit": "1040",
      "loan": "1000",
      "status": "ACTIVE",
      "title": "1000 تتر اعتبار معاملاتی",
      "warning_limit": "1070"
    },
    {
      "assurance": "50",
      "currency": "USDT",
      "daily_fee": "0.2",
      "daily_fee_after_discount": "0.2",
      "daily_fee_discount": "0",
      "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/dENZiRwyoSLtSuRgspmIIIBfQCADeysjFsTS6Fcz.png",
      "destination_currency": null,
      "expire_days": 30,
      "final_fee": "6",
      "final_fee_after_discount": "6",
      "final_fee_discount": "0",
      "id": 143,
      "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/Y6gfyqFrnngQJDFmw3fI9CJ0x3MHKGuLhwRYuPu6.png",
      "liquidity_limit": "416",
      "loan": "400",
      "status": "ACTIVE",
      "title": "400 تتر اعتبار معاملاتی",
      "warning_limit": "428"
    },
    {
      "assurance": "2000000",
      "currency": "TMN",
      "daily_fee": "30000",
      "daily_fee_after_discount": "30000",
      "daily_fee_discount": "0",
      "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/PCehq12IOqO6u2TE0apKRr75sTTdrYu8RPsr4fHU.png",
      "destination_currency": null,
      "expire_days": 30,
      "final_fee": "900000",
      "final_fee_after_discount": "900000",
      "final_fee_discount": "0",
      "id": 131,
      "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/MuIyDfbsdCTMFcF9bSyWQNEaAkVLPdCX93PR27tv.png",
      "liquidity_limit": "30900000",
      "loan": "30000000",
      "status": "ACTIVE",
      "title": "۳۰ میلیون اعتبار معاملاتی",
      "warning_limit": "31200000"
    },
    {
      "assurance": "200",
      "currency": "USDT",
      "daily_fee": "1",
      "daily_fee_after_discount": "1",
      "daily_fee_discount": "0",
      "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/sFhEQtqD2k38ygKDMhydTFROej0VRcnE48pB2iP9.png",
      "destination_currency": null,
      "expire_days": 30,
      "final_fee": "30",
      "final_fee_after_discount": "30",
      "final_fee_discount": "0",
      "id": 140,
      "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/6qSIvatJ9EYAvuEfP2k7f1eJiwh8HuIyy4HxZNao.png",
      "liquidity_limit": "2080",
      "loan": "2000",
      "status": "ACTIVE",
      "title": "۲۰۰۰ تتر اعتبار معاملاتی",
      "warning_limit": "2140"
    },
    {
      "assurance": "100",
      "currency": "USDT",
      "daily_fee": "0.5",
      "daily_fee_after_discount": "0.5",
      "daily_fee_discount": "0",
      "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/6TBRjooe1smhFFVvctn5mXWQyYgGQHnQ4KP6kGzC.png",
      "destination_currency": null,
      "expire_days": 30,
      "final_fee": "15",
      "final_fee_after_discount": "15",
      "final_fee_discount": "0",
      "id": 122,
      "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/CZ5WKgLjqobOjI0v5ssITkFFgbNT6PB4UAuIqbdo.png",
      "liquidity_limit": "1040",
      "loan": "1000",
      "status": "ACTIVE",
      "title": "1000 تتر اعتبار معاملاتی",
      "warning_limit": "1070"
    },
    {
      "assurance": "20000000",
      "currency": "TMN",
      "daily_fee": "200000",
      "daily_fee_after_discount": "200000",
      "daily_fee_discount": "0",
      "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/NDHttjNUufen1eGvqy15KQf14YmkJeCjZpjIjS7R.svg",
      "destination_currency": null,
      "expire_days": 30,
      "final_fee": "6000000",
      "final_fee_after_discount": "6000000",
      "final_fee_discount": "0",
      "id": 113,
      "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/AfCYnScOe5cQ148IcTnHsVCNvqLmwP626dazZUDB.svg",
      "liquidity_limit": "208000000",
      "loan": "200000000",
      "status": "ACTIVE",
      "title": "200 میلیون اعتبار معاملاتی",
      "warning_limit": "214000000"
    },
    {
      "assurance": "1000000",
      "currency": "TMN",
      "daily_fee": "10000",
      "daily_fee_after_discount": "10000",
      "daily_fee_discount": "0",
      "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/1rX2EiHtSN0pm8wY5IeeD0PVFfPV8YtARYhS5K1u.png",
      "destination_currency": null,
      "expire_days": 30,
      "final_fee": "300000",
      "final_fee_after_discount": "300000",
      "final_fee_discount": "0",
      "id": 101,
      "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/4cyZKkkKacBAEOMYrBqCmKdTlL4RWey1anAEjwQk.png",
      "liquidity_limit": "10400000",
      "loan": "10000000",
      "status": "ACTIVE",
      "title": "10 میلیون اعتبار معاملاتی",
      "warning_limit": "10700000"
    },
    {
      "assurance": "5000000",
      "currency": "TMN",
      "daily_fee": "25000",
      "daily_fee_after_discount": "25000",
      "daily_fee_discount": "0",
      "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/dsKIHlBwaDFYi1ZDuZFkpEmdEROoksIHJoumAUYv.png",
      "destination_currency": null,
      "expire_days": 30,
      "final_fee": "750000",
      "final_fee_after_discount": "750000",
      "final_fee_discount": "0",
      "id": 110,
      "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/iIDmZchey8NNFvrj4kqSz0uqFNe7ccGwpGVDKAIz.png",
      "liquidity_limit": "26000000",
      "loan": "25000000",
      "status": "ACTIVE",
      "title": "25 میلیون اعتبار معاملاتی",
      "warning_limit": "26750000"
    },
    {
      "assurance": "10000000",
      "currency": "TMN",
      "daily_fee": "50000",
      "daily_fee_after_discount": "50000",
      "daily_fee_discount": "0",
      "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/Xa7dc76ouezN2vAtmi1yFW4ZNADyhQfJTBycq2Nm.png",
      "destination_currency": null,
      "expire_days": 30,
      "final_fee": "1500000",
      "final_fee_after_discount": "1500000",
      "final_fee_discount": "0",
      "id": 79,
      "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/PUqIeYEOLP9WOLTZCIxpU4bL5NRF6lwDDnwd7tCE.png",
      "liquidity_limit": "52000000",
      "loan": "50000000",
      "status": "ACTIVE",
      "title": "50 میلیون اعتبار معاملاتی",
      "warning_limit": "53500000"
    },
    {
      "assurance": "20000000",
      "currency": "TMN",
      "daily_fee": "100000",
      "daily_fee_after_discount": "100000",
      "daily_fee_discount": "0",
      "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/KOi8SROWgHh4UDRD3p4VHdPlaBJRVgjic6ry94Yb.png",
      "destination_currency": null,
      "expire_days": 30,
      "final_fee": "3000000",
      "final_fee_after_discount": "3000000",
      "final_fee_discount": "0",
      "id": 104,
      "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/9Hu9vt5HFlUxNKxKLmd6oqeAoiiMtqIWb9MCiRom.png",
      "liquidity_limit": "104000000",
      "loan": "100000000",
      "status": "ACTIVE",
      "title": "100 میلیون اعتبار معاملاتی",
      "warning_limit": "107000000"
    },
    {
      "assurance": "10000000",
      "currency": "TMN",
      "daily_fee": "40000",
      "daily_fee_after_discount": "40000",
      "daily_fee_discount": "0",
      "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/qojEXt6QjlMdO2YprMFIV1x2TCjWCtawrWBu0Jvy.png",
      "destination_currency": null,
      "expire_days": 30,
      "final_fee": "1200000",
      "final_fee_after_discount": "1200000",
      "final_fee_discount": "0",
      "id": 76,
      "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/KaLDBDgyIROq2LimeKpG5pjnehswRCdpln5cqtcV.png",
      "liquidity_limit": "41600000",
      "loan": "40000000",
      "status": "ACTIVE",
      "title": "40 میلیون اعتبار معاملاتی",
      "warning_limit": "42800000"
    },
    {
      "assurance": "100000000",
      "currency": "TMN",
      "daily_fee": "300000",
      "daily_fee_after_discount": "300000",
      "daily_fee_discount": "0",
      "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/Rn7TVSIEzfZFyc5vuheqKFoNCkuouJFYxJlNkOAF.png",
      "destination_currency": null,
      "expire_days": 30,
      "final_fee": "9000000",
      "final_fee_after_discount": "9000000",
      "final_fee_discount": "0",
      "id": 97,
      "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/EOmEhwaJKwnhnVhjg7OeGKQYh5duOS5gGARpwGUX.png",
      "liquidity_limit": "312000000",
      "loan": "300000000",
      "status": "ACTIVE",
      "title": "300 میلیون اعتبار معاملاتی",
      "warning_limit": "321000000"
    },
    {
      "assurance": "10000000",
      "currency": "TMN",
      "daily_fee": "30000",
      "daily_fee_after_discount": "30000",
      "daily_fee_discount": "0",
      "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/mDBahzwIu2UdDZ37Dy56hU2bI6V7DAKZltVGK1xk.png",
      "destination_currency": null,
      "expire_days": 30,
      "final_fee": "900000",
      "final_fee_after_discount": "900000",
      "final_fee_discount": "0",
      "id": 73,
      "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/F2doDvaz24YhvTdhWMVpBECtvQgvz7R11qQTypHe.png",
      "liquidity_limit": "32136000",
      "loan": "30000000",
      "status": "INACTIVE",
      "title": "30 میلیون اعتبار معاملاتی",
      "warning_limit": "34715000"
    },
    {
      "assurance": "50000000",
      "currency": "TMN",
      "daily_fee": "150000",
      "daily_fee_after_discount": "150000",
      "daily_fee_discount": "0",
      "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/1b4UBGRgGfTXLsOmkKWxxrtYXrAuB9cLQblRcULx.png",
      "destination_currency": null,
      "expire_days": 30,
      "final_fee": "4500000",
      "final_fee_after_discount": "4500000",
      "final_fee_discount": "0",
      "id": 91,
      "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/jdU7JWXampXUCezLgN0JD6Bga3mYMBNAEJaFhEhu.png",
      "liquidity_limit": "156000000",
      "loan": "150000000",
      "status": "ACTIVE",
      "title": "150 میلیون اعتبار معاملاتی",
      "warning_limit": "160500000"
    },
    {
      "assurance": "20000000",
      "currency": "TMN",
      "daily_fee": "60000",
      "daily_fee_after_discount": "60000",
      "daily_fee_discount": "0",
      "dark_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/oreeZUbvdF8iwORrpV7RXCbfiCRShqCgK6R5syxO.png",
      "destination_currency": null,
      "expire_days": 30,
      "final_fee": "1800000",
      "final_fee_after_discount": "1800000",
      "final_fee_discount": "0",
      "id": 82,
      "light_image_url": "https://s3.thr1.sotoon.ir/wallex-public/packages/aR8eaa37bYiH6FxF7wMnp5kGzVrK4Yr07C2bzeZz.png",
      "liquidity_limit": "62400000",
      "loan": "60000000",
      "status": "INACTIVE",
      "title": "60 میلیون اعتبار معاملاتی",
      "warning_limit": "64200000"
    }
  ],
  "success": true
}
```

</details>
