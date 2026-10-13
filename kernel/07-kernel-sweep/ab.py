# -*- coding: utf-8 -*-
"""A/B: same items, two card revisions, one attempt each (isolates card effect from transport)."""
import sys,io,time,json,os
sys.path.insert(0,'.')
import sweep as S
HERE=os.path.dirname(os.path.abspath(__file__))
CARDS=os.path.join(HERE,'..','04-console','cards','base')
MODEL=sys.argv[1]
ITEMS=sys.argv[2].split(',')
CUR=io.open(os.path.join(CARDS,sys.argv[3]),encoding='utf-8').read()
OLD=io.open(os.path.join(HERE,'_backup-r2',sys.argv[3]),encoding='utf-8').read()
Q={i:t for i,t in S.ITEMS}
for tag,card in [("r1card",OLD),("r2card",CUR)]:
    for i in ITEMS:
        t0=time.time(); t,rea,us,st=S.raw(MODEL,card,Q[i]); dt=round(time.time()-t0,1)
        v,sig=S.score(i,t,st)
        print("%-7s %-4s %-8s %6.1fs len=%-6d %s"%(tag,i,v,dt,len(t),(t[:110].replace('\n',' '))),flush=True)
