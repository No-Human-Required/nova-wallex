# Wallex API Documentation (offline copy)

Offline Markdown copy of <https://developers.wallex.ir/docs/>, fetched 2026-11-04.
Most guide pages are in Persian (Farsi); the auto-generated API reference pages are in English.

## Layout

- `*.md` — guide pages (one file per page, same slug as the website URL)
- `generated/*.md` — endpoint reference pages, built from the site's OpenAPI data (method, path, auth, parameters, request body, response schemas)
- `openapi/*.openapi.json` — OpenAPI 3 specs rebuilt from the same data, one per API group (spot, trade-credit, wallex-margin-trade-api)

Auth: private endpoints use the `x-api-key` header (see [create-api-key.md](./create-api-key.md)). Base URL: `https://api.wallex.ir`.

## Table of contents (website sidebar order)

- [پیش‌گفتار](./index.md)
- [ساخت API-Key](./create-api-key.md)
- **سرویس‌های پایه**
  - [مقدمه](./basic-services.md)
  - [کیف‌پول حساب اصلی](./basic-services-main-wallet.md)
  - [کندل‌ها](./basic-services-candles.md)
  - [مارکت‌ها](./basic-services-markets.md)
  - [عمق بازار](./basic-services-depth.md)
  - [لیست معاملات](./basic-services-latest-trades.md)
  - [کارمزد حساب کاربری](./basic-services-account-fee.md)
  - [اضافه کردن شماره شبا بانکی](./basic-services-add-iban.md)
  - [دریافت شماره‌های شبا بانکی](./basic-services-iban-numbers.md)
  - [دریافت کارت‌های بانکی](./basic-services-card-numbers.md)
  - [ثبت درخواست برداشت تومان](./basic-services-withdraw-toman.md)
  - [برداشت رمزارز](./basic-services-crypto-withdrawal.md)
  - [دریافت آدرس کیف‌پول رمزارز](./basic-services-coin-wallets.md)
  - **مستندات سرویس**
    - [دریافت آدرس کیف‌پول کاربر برای نماد مشخص](./generated/get-account-wallet-by-symbol.md) — `GET /v1/account/wallets/{symbol}`
    - [افزودن شماره شبا جدید به حساب](./generated/add-account-iban.md) — `POST /v1/account/ibans`
    - [دریافت لیست شماره شباهای حساب](./generated/get-account-ibans.md) — `GET /v1/account/ibans`
    - [درخواست برداشت وجه از حساب](./generated/create-money-withdrawal.md) — `POST /v1/account/money-withdrawal`
    - [ثبت درخواست برداشت رمزارز](./generated/create-crypto-withdrawal.md) — `POST /v1/account/crypto-withdrawal`
    - [دریافت فهرست برداشت‌های رمزارز](./generated/list-crypto-withdrawals.md) — `GET /v1/account/crypto-withdrawal`
    - [دریافت جزئیات برداشت رمزارز](./generated/get-crypto-withdrawal.md) — `GET /v1/account/crypto-withdrawal/{withdrawal_id}`
    - [دریافت شماره کارت‌های بانکی حساب](./generated/get-account-card-numbers.md) — `GET /v1/account/card-numbers`
    - [دریافت کارمزدهای حساب](./generated/get-account-fees.md) — `GET /v1/account/fee`
    - [دریافت معاملات اخیر](./generated/get-latest-trades.md) — `GET /v1/trades`
    - [Get all markets ](./generated/get-markets.md) — `GET /hector/web/v1/markets`
    - [دریافت عمق بازار](./generated/get-market-depth.md) — `GET /v1/depth`
    - [Get account balances](./generated/get-account-balances.md) — `GET /v1/account/balances`
    - [Get historical market data (candles)](./generated/candle-history.md) — `GET /v1/udf/history`
- **معامله اسپات**
  - [معامله اسپات چیست؟](./spot-intro.md)
  - [اصطلاحات معامله اسپات](./spot-types.md)
  - [مارکت‌های فعال در معامله اسپات](./spot-active-markets.md)
  - [ثبت سفارش اسپات](./spot-create-order.md)
  - [لغو سفارش](./spot-cancel-order.md)
  - [دریافت جزئیات سفارش](./spot-single-order-detail.md)
  - [لیست تمامی سفارشات](./spot-order-list.md)
  - [لیست سفارشات فعال](./spot-active-orders.md)
  - **مستندات سرویس**
    - [Get all markets ](./generated/get-markets.md) — `GET /hector/web/v1/markets`
    - [Get all markets depth](./generated/get-depth.md) — `GET /depth/all`
    - [List active orders](./generated/get-open-order.md) — `GET /v1/account/openOrders`
    - [List margin orders](./generated/get-orders.md) — `GET /margin-trade/v1/orders`
    - [Submit a new trading order](./generated/post-account-orders.md) — `POST /v1/account/orders`
    - [Cancel an existing order](./generated/delete-account-orders.md) — `DELETE /v1/account/orders`
    - [Get order details](./generated/get-orders-client.md) — `GET /v1/account/orders/{client_id}`
    - [Cancel an order by path parameter](./generated/delete-orders-client.md) — `DELETE /v1/account/orders/{client_id}`
- **معامله تعهدی**
  - [معامله تعهدی چیست؟](./margin-intro.md)
  - [اصطلاحات معامله تعهدی](./margin-types.md)
  - [مارکت‌های فعال در معامله تعهدی](./margin-active-markets.md)
  - [محاسبه وثیقه](./margin-calculate-loan.md)
  - [اطلاعات کامل موقعیت قبل باز شدن](./margin-dry-run.md)
  - [باز کردن موقعیت تعهدی](./margin-open-position.md)
  - [دریافت موقعیت‌های تعهدی](./margin-get-positions.md)
  - [ویرایش وثیقه موقعیت تعهدی](./margin-edit-collateral.md)
  - [ویرایش حد سود و ضرر](./margin-sltp-edit.md)
  - [بستن موقعیت](./margin-close-position.md)
  - **مستندات سرویس**
    - [List margin orders](./generated/get-orders.md) — `GET /margin-trade/v1/orders`
    - [List margin positions](./generated/get-positions.md) — `GET /margin-trade/v1/positions`
    - [Open a margin position](./generated/open-position.md) — `POST /margin-trade/v1/positions`
    - [Get a margin position](./generated/get-position-id.md) — `GET /margin-trade/v1/positions/{id}`
    - [Close a margin position](./generated/close-position-id.md) — `PATCH /margin-trade/v1/positions/{id}/close`
    - [Update margin positions collateral](./generated/edit-colateral.md) — `PATCH /margin-trade/v1/positions/{id}/collateral`
    - [Calculate](./generated/profit-position-id.md) — `POST /margin-trade/v1/positions/{id}/profit`
    - [Update stop-loss and take-profit prices](./generated/edit-sltp.md) — `PATCH /margin-trade/v1/positions/{id}/sltp`
    - [calculate min, max Collateral and loan](./generated/calculate-loan.md) — `POST /margin-trade/v1/public/loan`
    - [info a margin position before creation](./generated/detailed-information.md) — `POST /margin-trade/v1/public/dry-run`
    - [Get all markets ](./generated/get-markets.md) — `GET /hector/web/v1/markets`
    - [Positions Ratio of long and short](./generated/public-ratio.md) — `GET /margin-trade/v1/public/ratio/{market}`
    - [margin trade user levels](./generated/get-levels.md) — `GET /margin-trade/v1/user/levels`
    - [margin trade user levels](./generated/get-levels-market.md) — `GET /margin-trade/v1/user/levels/{market}`
    - [User PNL](./generated/get-pnl.md) — `GET /margin-trade/v1/user/pnl`
- **اعتبار معاملاتی**
  - [اعتبار معاملاتی چیست؟](./trade-credit-intro.md)
  - [اصطلاحات اعتبار معاملاتی](./trade-credit-types.md)
  - [پکیج‌های فعال اعتبار معاملاتی](./trade-credit-active-packages.md)
  - [دریافت جزیيات پکیج و لیست بازارهای غیر فعال](./trade-credit-package-details.md)
  - [بررسی شرایط کاربر برای دریافت اعتبار معاملاتی](./trade-credit-condition-check.md)
  - [فعال کردن پکیج اعتبار معاملاتی](./trade-credit-activate-sub-account.md)
  - [اتصال کیف پول اصلی به اکانت اعتبار معاملاتی](./trade-credit-connect-wallet.md)
  - [قطع اتصال کیف پول اصلی از اکانت اعتبار معاملاتی](./trade-credit-disconnect-wallet.md)
  - [بستن اکانت اعتبار معاملاتی](./trade-credit-close-sub-account.md)
  - [دریافت تاریخچه طرح های اعتبار معاملاتی](./trade-credit-sub-account-history.md)
  - [لیست حساب های اعتبار معاملاتی](./trade-credit-active-sub-account-list.md)
  - **مستندات سرویس**
    - [Active Sub Accounts List](./generated/active-sub-accounts-list.md) — `GET /sub-accounts`
    - [List Sub Account Transfers](./generated/sub-account-transfer.md) — `GET /sub-accounts/transfers`
    - [Create Transfer To Sub Account](./generated/create-transfer-to-sub-account.md) — `POST /sub-accounts/transfers`
    - [Sub Account Balances Details](./generated/sub-account-balances-details.md) — `GET /v1/account/balances-detail`
    - [Prop Packages List](./generated/prop-packages-list.md) — `GET /v1/prop/packages`
    - [Prop Package Details](./generated/prop-package-details.md) — `GET /v1/prop/packages/{id}`
    - [User Package History List](./generated/user-package-history-list.md) — `GET /v1/prop/user/packages/history`
    - [User Package History Details](./generated/user-package-history-details.md) — `GET /v1/prop/user/packages/history/{subAccountClientId}`
    - [Active User Packages Overview](./generated/active-user-packages-overview.md) — `GET /v1/prop/user/packages/overview`
    - [Active User Package Details](./generated/active-user-package-details.md) — `GET /v1/prop/user/packages/active`
    - [Check Prop Package Availability](./generated/check-prop-package-availability.md) — `GET /v1/prop/user/packages/{id}/check-availability`
    - [Activate User Package](./generated/activate-user-package.md) — `POST /v1/prop/user/packages`
    - [Cancel User Package](./generated/cancel-user-package.md) — `DELETE /v1/prop/user/packages`
    - [Enable Connect To Wallet](./generated/enable-connect-to-wallet.md) — `POST /v1/prop/user/packages/connect-to-wallet`
    - [Disable Connect To Wallet](./generated/disable-connect-to-wallet.md) — `DELETE /v1/prop/user/packages/connect-to-wallet`
    - [Enable User Package Renew](./generated/enable-user-package-renew.md) — `POST /v1/prop/user/packages/enable-renew`
- **معامله آنی**
  - [خرید و فروش در بازار معاملاتی آنی چیست ؟](./otc-intro.md)
  - [بازارهای فعال در معاملات آنی](./otc-markets.md)
  - [دریافت قیمت ها در بازار آنی](./otc-price.md)
  - [ثبت سفارش در بازار آنی](./otc-create-order.md)
  - **مستندات سرویس**
    - [get otc markets](./generated/get-otc-markets.md) — `GET /v1/otc/markets`
    - [get otc price](./generated/get-otc-price.md) — `GET /v1/account/otc/price`
    - [create otc trade](./generated/place-easy-trade-order.md) — `POST /v1/account/easy-trade/orders`
- **وب‌سوکت**
  - [سوکت های والکس](./socket-intro.md)
  - [راهنمای مهاجرت](./socket-migration.md)
  - [اتصال و عضویت (با SDK)](./socket-connection.md)
  - [اتصال بدون SDK](./socket-raw-protocol.md)
  - [توکن اتصال خصوصی](./socket-token.md)
  - [دریافت عمق بازار خرید](./socket-buy-depth.md)
  - [دریافت عمق بازار فروش](./socket-sell-depth.md)
  - [دریافت معاملات انجام‌شده](./socket-trade.md)
  - [دریافت قیمت لحظه‌ای](./socket-all-price.md)
  - [رویدادهای خصوصی کاربران](./socket-private-channel.md)
  - [تغییرات کندل چارت](./socket-candle.md)
  - [دریافت قیمت منصفانه](./socket-fair-price.md)

## Pages not in the sidebar

- [trade-credit-wallet](./trade-credit-wallet.md)
- [trade-credit](./generated/trade-credit.md)
- [Wallex Margin-trade API](./generated/wallex-margin-trade-api.md)
- [trade-credit-sub-account-transfer](./trade-credit-sub-account-transfer.md)
- [Spot](./generated/spot.md)
