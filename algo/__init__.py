"""Algorithmic (الگوریتمیک): multi-user trading-bot platform built on Nova's engine core.

A separate application from Nova's account engine: its own process, database
namespace and container. Users sign in with an SMS one-time code, build and
backtest bots, run them on paper and, after admin approval, on their own
exchange account. The back office manages users, plans, payments, approvals
and every provider setting.
"""
VERSION = '1.3.0'
