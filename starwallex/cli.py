import argparse
import json
from pathlib import Path
from .domain import load_config
from .util import ROOT, canonical


def main():
    parser=argparse.ArgumentParser(description="Wallex shadow-only research engine; exchange writes unavailable")
    parser.add_argument("--config",type=Path,default=ROOT/"config/shadow.json")
    sub=parser.add_subparsers(dest="command",required=True)
    c=sub.add_parser("collect");c.add_argument("--days",type=int,default=21)
    e=sub.add_parser("evaluate");e.add_argument("--out",type=Path,required=True);e.add_argument("--with-ai",action="store_true");e.add_argument("--replay-only",action="store_true")
    s=sub.add_parser("shadow");s.add_argument("--out",type=Path,required=True);s.add_argument("--cycles",type=int,default=3);s.add_argument("--poll-seconds",type=int,default=15)
    r=sub.add_parser("report");r.add_argument("directory",type=Path)
    sub.add_parser("live")
    args=parser.parse_args()
    cfg=load_config(args.config)
    if args.command=="live":
        parser.error("LIVE DISABLED by user instruction. This release contains no exchange order transport.")
    if args.command=="collect":
        from .data import collect
        print(canonical([{**r,"gaps":len(r["gaps"])} for r in collect(args.days,cfg["research_symbols"])]))
    elif args.command=="evaluate":
        from .evaluate import evaluate
        from .report import report
        rows=evaluate(cfg,args.out,with_ai=args.with_ai,replay_only=args.replay_only)
        report(args.out)
        print(canonical([{k:r[k] for k in ["symbol","split","policy","net_return_percent","max_drawdown_percent","fill_count","ai_changed_actions"]} for r in rows]))
    elif args.command=="shadow":
        from .shadow import shadow
        print(canonical(shadow(cfg,args.out,cycles=args.cycles,poll_seconds=args.poll_seconds)))
    else:
        from .report import report
        print(report(args.directory))


if __name__=="__main__":
    main()
